"""Hybrid geocoder: Google trước, LLM fallback. Trả `GeocodeOutcome` (WGS84).

Google Geocoding API lo các địa danh CÒN tồn tại đúng tên (toạ độ chính xác), KỂ CẢ
địa danh nước ngoài (Paris, Genève, Trung Quốc, đảo Rêuyniông... — corpus lịch sử VN có
nhiều sự kiện ở ngoài nước); địa danh Google không tìm được (đã đổi tên / căn cứ lịch sử
/ biến mất) -> LLM suy toạ độ gần đúng kèm confidence thấp hơn cho review tay. KHÔNG ép
chỉ-Việt-Nam: chỉ `region=vn` để BIAS ưu tiên địa danh VN khi trùng tên, không lọc cứng.
Mọi toạ độ là WGS84 nên đổi provider sau này chỉ cần viết một adapter `_xxx_geocode()`
thay cho `_google_geocode()`.

LƯU Ý ToS: Google Maps Platform chỉ cho cache lat/lon tối đa 30 ngày (place_id được lưu
vô thời hạn). Cache `gazetteer.json` lưu lâu hơn là rủi ro tuân thủ — xem
docs/reference/google-maps-api.md §4.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from contextlib import nullcontext
from typing import Literal

import httpx
from openai import OpenAI

from app.core.config import get_settings
from app.core.llm import get_openai_client
from app.prompts.geocode import (
    GEOCODE_PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_user_prompt,
)
from app.schemas.gazetteer import GeocodeOutcome, GeocodeResult

__all__ = ["geocode_location", "GEOCODE_PROMPT_VERSION", "VN_BBOX", "in_vietnam"]

log = logging.getLogger(__name__)

# bbox lãnh thổ VN (WGS84). Khớp khoảng nêu trong schema GeocodeResult. Là helper tiện
# ích (vd UI canh khung map / cờ marker ngoài nước), KHÔNG còn dùng để lọc cứng kết quả
# geocode — địa danh nước ngoài vẫn được chấp nhận.
VN_LAT_MIN, VN_LAT_MAX = 8.0, 23.5
VN_LON_MIN, VN_LON_MAX = 102.0, 110.0
VN_BBOX = (VN_LAT_MIN, VN_LAT_MAX, VN_LON_MIN, VN_LON_MAX)

_GOOGLE_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"


def in_vietnam(lat: float, lon: float) -> bool:
    return VN_LAT_MIN <= lat <= VN_LAT_MAX and VN_LON_MIN <= lon <= VN_LON_MAX


# y->i hợp nhất chính tả cũ/mới (Mĩ/Mỹ, kĩ/kỹ) NHƯNG GIỮ dấu thanh: ánh xạ từng biến
# thể có dấu của 'y' sang 'i' cùng dấu (ý->í, ỳ->ì, ỷ->ỉ, ỹ->ĩ, ỵ->ị, y->i).
_Y_TO_I = str.maketrans("yýỳỷỹỵ", "iíìỉĩị")


def _fold(text: str) -> str:
    """Chuẩn hoá tên để so khớp: hạ thường + NFC + y->i. **GIỮ DẤU.**

    Google Geocoding với `language=vi` luôn trả `formatted_address` CÓ DẤU (kiểm bằng API
    thật: "Gia Định", "Cần Giờ", "Quảng Châu, Quảng Đông, Trung Quốc"...), nên KHÔNG bỏ
    dấu — bỏ dấu sẽ làm "Chợ Lớn" trùng "Chơ Long" sai nghĩa. Chỉ y->i để hợp nhất biến
    thể chính tả cũ/mới (Mĩ/Mỹ, kĩ/kỹ), giữ nguyên dấu thanh. NFC để precomposed/combining
    về một dạng; regex thay ký tự không phải chữ/số (dấu phẩy, gạch nối) bằng khoảng trắng.
    """
    text = unicodedata.normalize("NFC", text.lower()).translate(_Y_TO_I)
    return re.sub(r"[^\w\s]", " ", text)


def _name_matches(query: str, candidate: str) -> bool:
    """True nếu MỌI token tên truy vấn đều có trong tên Google trả về (so khớp giữ dấu).

    Chặn fuzzy-match: Google luôn trả "đại khái" một kết quả kể cả khi không khớp
    (vd 'Bình Cách' -> 'Cách Mạng Tháng Tám', 'Sơn Trà' -> 'Trần Quốc Thảo'; thường
    kèm cờ `partial_match=true`). Nếu token tên truy vấn không nằm trong
    `formatted_address` -> coi như Google KHÔNG tìm thấy.
    """
    q_tokens = _fold(query).split()
    c_tokens = set(_fold(candidate).split())
    return bool(q_tokens) and all(tok in c_tokens for tok in q_tokens)


def _confidence_from_types(types: list[str]) -> Literal["cao", "vừa", "thấp"]:
    """Suy confidence từ mảng `types` của kết quả Google Geocoding.

    'country' = chỉ khớp tới mức quốc gia (không định vị được nơi cụ thể) -> thấp.
    'administrative_area_level_1' = cấp tỉnh/thành (khá thô) -> vừa. Cụ thể hơn
    (locality/administrative_area_level_2/sublocality/route/...) -> cao.
    """
    if "country" in types:
        return "thấp"
    if "administrative_area_level_1" in types:
        return "vừa"
    return "cao"


def _google_geocode(
    name: str, api_key: str, *, http_client: httpx.Client
) -> GeocodeOutcome | None:
    """Gọi Google Geocoding (region=vn chỉ BIAS, cho phép cả địa danh nước ngoài).

    None nếu không tìm được / lỗi. KHÔNG lọc theo bbox VN: sự kiện lịch sử VN có nhiều
    địa danh ở ngoài nước (Paris, Genève, Trung Quốc...) cần geocode đúng.
    """
    try:
        resp = http_client.get(
            _GOOGLE_GEOCODE_URL,
            params={
                "address": name,
                "key": api_key,
                "language": "vi",
                "region": "vn",  # chỉ bias ưu tiên VN khi trùng tên, KHÔNG lọc cứng
            },
            timeout=30,
        )
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        log.warning("Google geocode lỗi khi geocode %r: %s", name, exc)
        return None

    body = resp.json()
    # Google trả HTTP 200 kèm status lỗi trong body -> phải kiểm tra status thủ công.
    status = str(body.get("status") or "")
    if status != "OK":
        if status not in ("ZERO_RESULTS", ""):
            log.warning(
                "Google geocode status %s cho %r: %s",
                status,
                name,
                body.get("error_message", ""),
            )
        return None

    results = body.get("results") or []
    if not results:
        return None
    res = results[0]
    loc = (res.get("geometry") or {}).get("location") or {}
    lat_raw, lng_raw = loc.get("lat"), loc.get("lng")
    if lat_raw is None or lng_raw is None:
        return None
    lat, lon = float(lat_raw), float(lng_raw)  # Google: location.{lat,lng} tách rõ
    types = [str(t) for t in (res.get("types") or [])]
    display = str(res.get("formatted_address") or name)
    # Chặn fuzzy-match: nếu tên Google trả về không chứa đủ token tên truy vấn ->
    # coi như không tìm thấy, để LLM (biết ngữ cảnh lịch sử) lo.
    if not _name_matches(name, display):
        log.debug("Google khớp nhầm %r -> %r; bỏ, dùng LLM fallback.", name, display)
        return None
    return GeocodeOutcome(
        lat=lat,
        lon=lon,
        confidence=_confidence_from_types(types),
        resolved_by="google",
        provider_name=display,
        admin_level=types[0] if types else "",
    )


def _llm_geocode(name: str, *, client: OpenAI, model: str) -> GeocodeOutcome:
    """LLM suy toạ độ (fallback). 0.0/0.0 -> coi như không định vị được."""
    completion = client.chat.completions.parse(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(name)},
        ],
        response_format=GeocodeResult,
        timeout=60,
        temperature=0.0,
    )
    message = completion.choices[0].message
    if getattr(message, "refusal", None) or message.parsed is None:
        return GeocodeOutcome(resolved_by="none")

    result = message.parsed
    lat = result.lat if result.lat != 0.0 else None
    lon = result.lon if result.lon != 0.0 else None
    if lat is None or lon is None:
        return GeocodeOutcome(
            resolved_by="none",
            admin_level=result.admin_level,
            modern_name=result.modern_name,
            note=result.note,
        )
    return GeocodeOutcome(
        lat=lat,
        lon=lon,
        confidence=result.confidence,
        resolved_by="llm",
        provider_name=result.modern_name,
        admin_level=result.admin_level,
        modern_name=result.modern_name,
        note=result.note,
    )


def geocode_location(
    name: str,
    *,
    google_api_key: str | None = None,
    http_client: httpx.Client | None = None,
    client: OpenAI | None = None,
    model: str | None = None,
) -> GeocodeOutcome:
    """Geocode một địa danh: Google trước, LLM fallback. Luôn trả GeocodeOutcome.

    `google_api_key` None -> lấy từ settings (rỗng -> bỏ Google, chỉ LLM). Truyền
    `http_client`/`client` dùng chung khi gọi hàng loạt (build_gazetteer) để tái dùng
    kết nối.
    """
    name = (name or "").strip()
    if not name:
        return GeocodeOutcome(resolved_by="none")

    settings = get_settings()
    api_key = settings.google_maps_api_key if google_api_key is None else google_api_key

    # 1) Google trước. Dùng client truyền vào (gọi hàng loạt) hoặc tự mở một cái tạm.
    if api_key:
        ctx = nullcontext(http_client) if http_client is not None else httpx.Client()
        with ctx as hc:
            out = _google_geocode(name, api_key, http_client=hc)
        if out is not None:
            return out

    # 2) LLM fallback.
    client = client or get_openai_client()
    model = model or settings.llm_model
    return _llm_geocode(name, client=client, model=model)
