"""Test geocoder hybrid: VN bbox, parse Google Geocoding, fallback LLM — mock, không gọi mạng."""

from __future__ import annotations

import httpx

from app.indexing.geocoding import geocoder as G
from app.schemas.gazetteer import GeocodeContext, GeocodeOutcome, GeocodeResult

def test_in_vietnam() -> None:
    assert G.in_vietnam(21.0285, 105.8542)  # Hà Nội
    assert not G.in_vietnam(48.8566, 2.3522)  # Paris
    assert not G.in_vietnam(0.0, 0.0)

def test_confidence_from_types() -> None:
    assert G._confidence_from_types(["locality", "political"]) == "cao"
    assert G._confidence_from_types(["administrative_area_level_2", "political"]) == "cao"
    assert G._confidence_from_types(["administrative_area_level_1", "political"]) == "vừa"
    assert G._confidence_from_types(["country", "political"]) == "thấp"
    assert G._confidence_from_types([]) == "cao"

def _mock_client(payload: dict, status: int = 200) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(lambda _req: httpx.Response(status, json=payload)))

def _google_ok(lat: float, lng: float, formatted: str, types: list[str]) -> dict:
    """Dựng body Google Geocoding status=OK với 1 kết quả."""
    return {
        "status": "OK",
        "results": [
            {
                "geometry": {"location": {"lat": lat, "lng": lng}},
                "formatted_address": formatted,
                "types": types,
            }
        ],
    }

def test_google_parse_lat_lng() -> None:
    # Google trả geometry.location.{lat,lng} tách rõ (không đảo như Mapbox [lon,lat]).
    payload = _google_ok(10.3539, 106.6678, "Gò Công, Tiền Giang, Việt Nam", ["locality", "political"])
    with _mock_client(payload) as c:
        out = G._google_geocode("Gò Công", "AIza.test", http_client=c)
    assert out is not None
    assert out.resolved_by == "google"
    assert abs(out.lat - 10.3539) < 1e-6
    assert abs(out.lon - 106.6678) < 1e-6
    assert out.confidence == "cao"
    assert "Gò Công" in out.provider_name

def test_google_zero_results_tra_none() -> None:
    with _mock_client({"status": "ZERO_RESULTS", "results": []}) as c:
        assert G._google_geocode("Địa danh lạ", "AIza.test", http_client=c) is None

def test_google_khop_nham_ten_bi_loai() -> None:
    # Google trả "đại khái" tên KHÁC hẳn (Bình Cách -> Cách Mạng Tháng Tám) -> phải bỏ.
    payload = _google_ok(15.1204, 108.8086, "Đường Cách Mạng Tháng Tám, Quảng Ngãi, Việt Nam", ["route"])
    with _mock_client(payload) as c:
        assert G._google_geocode("Bình Cách", "AIza.test", http_client=c) is None

def test_name_matches_giu_dau_va_i_y() -> None:
    # Google (language=vi) trả CÓ DẤU; so khớp GIỮ DẤU, chỉ hợp nhất y/i.
    assert G._name_matches("Mĩ Tho", "Mỹ Tho, Đồng Tháp, Việt Nam")  # i/y, giữ dấu
    assert G._name_matches("Gia Định", "Gia Định, Thành phố Hồ Chí Minh")  # đ + dấu khớp thẳng
    assert G._name_matches("Bà Rịa", "Bà Rịa - Sông Pha, Châu Pha")  # đúng tên dù type=street
    assert not G._name_matches("Chợ Lớn", "Chơ Long, Gia Lai")  # giữ dấu: Lớn != Long, Chợ != Chơ
    assert not G._name_matches("Sơn Trà", "Trần Quốc Thảo, Phan Rang")

def test_google_ngoai_vietnam_van_duoc() -> None:
    # KHÔNG ép VN: địa danh nước ngoài (Paris, Genève, Trung Quốc...) vẫn được chấp nhận.
    payload = _google_ok(48.8566, 2.3522, "Paris, Pháp", ["locality", "political"])
    with _mock_client(payload) as c:
        out = G._google_geocode("Paris", "AIza.test", http_client=c)
    assert out is not None
    assert out.resolved_by == "google"
    assert abs(out.lat - 48.8566) < 1e-6 and abs(out.lon - 2.3522) < 1e-6
    assert not G.in_vietnam(out.lat, out.lon)  # ngoài VN nhưng vẫn nhận

def test_google_status_loi_tra_none() -> None:
    # HTTP 200 nhưng status=REQUEST_DENIED (key sai/chưa bật API) -> None, để LLM lo.
    payload = {"status": "REQUEST_DENIED", "error_message": "The provided API key is invalid.", "results": []}
    with _mock_client(payload) as c:
        assert G._google_geocode("X", "AIza.bad", http_client=c) is None

def test_google_loi_http_tra_none() -> None:
    with _mock_client({"error": "forbidden"}, status=403) as c:
        assert G._google_geocode("X", "AIza.bad", http_client=c) is None

# --- Ngữ cảnh đi vào truy vấn Google ---

def test_google_address_ghep_vung_bao() -> None:
    ctx = GeocodeContext(anchors=["Điện Biên Phủ", "Lai Châu"], neighbors=["C1"], period="1954")
    # Chỉ anchor ĐẦU TIÊN; neighbors/period không vào truy vấn Google (chỉ làm nhiễu).
    assert G._google_address("đồi A1", ctx) == "đồi A1, Điện Biên Phủ"

def test_google_address_khong_co_nu_canh_giu_ten_tran() -> None:
    assert G._google_address("Hà Nội", None) == "Hà Nội"
    assert G._google_address("Hà Nội", GeocodeContext()) == "Hà Nội"

def test_google_address_bo_anchor_trung_chinh_ten() -> None:
    # "Mĩ Tho" vs "Mỹ Tho": _fold hợp nhất y/i -> coi là một, không ghép thành "X, X".
    assert G._google_address("Mĩ Tho", GeocodeContext(anchors=["Mỹ Tho"])) == "Mĩ Tho"

def test_google_gui_dung_address_co_vung_bao() -> None:
    seen: dict[str, str] = {}

    def _handler(req: httpx.Request) -> httpx.Response:
        seen["address"] = req.url.params["address"]
        return httpx.Response(200, json=_google_ok(21.38, 103.02, "A1, Điện Biên Phủ", ["premise"]))

    with httpx.Client(transport=httpx.MockTransport(_handler)) as c:
        G._google_geocode("A1", "AIza.test", http_client=c, context=GeocodeContext(anchors=["Điện Biên Phủ"]))
    assert seen["address"] == "A1, Điện Biên Phủ"

def test_google_van_doi_chieu_ten_TRAN_khong_phai_ten_da_ghep() -> None:
    # Truy vấn có anchor nhưng Google chỉ trả về đúng cái anchor -> khớp mờ, phải loại.
    payload = _google_ok(10.36, 106.67, "Tân An, Long An, Việt Nam", ["locality"])
    with _mock_client(payload) as c:
        out = G._google_geocode("Bình Cách", "AIza.test", http_client=c, context=GeocodeContext(anchors=["Tân An"]))
    assert out is None

def test_context_chay_toi_ca_hai_nhanh(monkeypatch) -> None:
    ctx = GeocodeContext(anchors=["Gò Công"])
    seen: dict[str, object] = {}

    def _google(*_a: object, context: object = None, **_k: object) -> None:
        seen["google"] = context
        return None  # miss -> ép đi tiếp xuống LLM

    def _llm(*_a: object, context: object = None, **_k: object) -> GeocodeOutcome:
        seen["llm"] = context
        return GeocodeOutcome()

    monkeypatch.setattr(G, "_google_geocode", _google)
    monkeypatch.setattr(G, "_llm_geocode", _llm)
    with _mock_client({}) as c:
        G.geocode_location("Tân Hòa", context=ctx, google_api_key="AIza.x", http_client=c, client=object(), model="m")  # type: ignore[arg-type]
    assert seen["google"] is ctx and seen["llm"] is ctx

# --- LLM path (fake client) ---

class _FakeMsg:
    refusal = None

    def __init__(self, parsed: GeocodeResult) -> None:
        self.parsed = parsed

class _FakeCompletions:
    def __init__(self, result: GeocodeResult) -> None:
        self._r = result

    def parse(self, **_kwargs: object) -> object:
        return type("C", (), {"choices": [type("Ch", (), {"message": _FakeMsg(self._r)})()]})()

class _FakeClient:
    def __init__(self, result: GeocodeResult) -> None:
        self.chat = type("Chat", (), {"completions": _FakeCompletions(result)})()

def test_llm_geocode_toa_do_0_la_khong_dinh_vi() -> None:
    r = GeocodeResult(lat=0.0, lon=0.0, confidence="thấp", admin_level="", modern_name="", note="mơ hồ")
    out = G._llm_geocode("Căn cứ vô danh", client=_FakeClient(r), model="m")  # type: ignore[arg-type]
    assert out.lat is None and out.lon is None
    assert out.resolved_by == "none"

def test_llm_geocode_hop_le() -> None:
    r = GeocodeResult(lat=21.0285, lon=105.8542, confidence="cao", admin_level="tỉnh", modern_name="", note="")
    out = G._llm_geocode("Hà Nội", client=_FakeClient(r), model="m")  # type: ignore[arg-type]
    assert out.resolved_by == "llm"
    assert abs(out.lat - 21.0285) < 1e-9

# --- Hybrid orchestration ---

def test_hybrid_dung_google_khi_tim_thay(monkeypatch) -> None:
    gg = GeocodeOutcome(lat=21.0, lon=105.8, confidence="cao", resolved_by="google")
    called = {"llm": False}
    monkeypatch.setattr(G, "_google_geocode", lambda *a, **k: gg)

    def _llm(*_a: object, **_k: object) -> GeocodeOutcome:
        called["llm"] = True
        return GeocodeOutcome()

    monkeypatch.setattr(G, "_llm_geocode", _llm)
    with _mock_client({}) as c:
        out = G.geocode_location("Hà Nội", google_api_key="AIza.x", http_client=c, client=object(), model="m")  # type: ignore[arg-type]
    assert out is gg
    assert called["llm"] is False  # Google trúng -> KHÔNG gọi LLM

def test_hybrid_fallback_llm_khi_google_miss(monkeypatch) -> None:
    sentinel = GeocodeOutcome(lat=10.0, lon=106.0, confidence="vừa", resolved_by="llm")
    monkeypatch.setattr(G, "_google_geocode", lambda *a, **k: None)
    monkeypatch.setattr(G, "_llm_geocode", lambda *a, **k: sentinel)
    with _mock_client({}) as c:
        out = G.geocode_location("Tân Hòa", google_api_key="AIza.x", http_client=c, client=object(), model="m")  # type: ignore[arg-type]
    assert out is sentinel
    assert out.resolved_by == "llm"
