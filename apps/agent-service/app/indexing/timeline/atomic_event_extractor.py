"""Trích danh sách "atomic event" (when–where–what) từ một unit bằng LLM.

Dùng OpenAI Structured Outputs (strict) qua `.parse()` -> output bảo đảm khớp
`TimelineExtraction`. Hàm thuần (chỉ I/O là LLM) để CLI gọi song song qua
ThreadPoolExecutor, giống khung `entity_relation_extractor.py`.

COMPLETENESS PASS: unit lớn (> ~40K ký tự) dễ bị LLM bỏ sót mốc ở phần đuôi context.
Với unit như vậy, gọi LẦN HAI kèm danh sách label đã trích, hỏi "còn mốc nào chưa
liệt kê?" rồi gộp các event mới (dedup theo label trong cùng unit). Dedup XUYÊN unit
là việc của reconcile (phase sau), không làm ở đây.
"""

from __future__ import annotations

import logging

from openai import OpenAI

from app.core.config import get_settings
from app.core.llm import get_openai_client
from app.prompts.timeline_extract import (
    TIMELINE_PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_user_prompt,
)
from app.schemas.timeline import AtomicEvent, TimelineExtraction

__all__ = ["TIMELINE_PROMPT_VERSION", "extract_timeline_events", "COMPLETENESS_CHAR_THRESHOLD"]

log = logging.getLogger(__name__)

_EMPTY = TimelineExtraction(events=[])

# Unit dài hơn ngưỡng này -> chạy thêm completeness pass chống sót ở đuôi context.
# Khớp cap segmenter (50K): nhóm ~10% unit lớn nhất rơi vào diện này.
COMPLETENESS_CHAR_THRESHOLD = 40_000


def _completeness_prompt(labels: str, headings: str, text: str) -> str:
    """Prompt lượt 2 hỏi phần bị sót (kèm danh sách label đã có)."""
    return (
        "Bạn đã trích các sự kiện sau từ đoạn văn (chỉ liệt kê label):\n"
        f"{labels}\n\n"
        "Hãy đọc LẠI toàn bộ đoạn và chỉ trả về NHỮNG sự kiện có diễn biến cụ thể mà "
        "bạn CHƯA liệt kê ở trên (bị bỏ sót). Tuân thủ đúng mọi quy tắc đã nêu. Nếu "
        "không còn sót gì, trả `events` rỗng. KHÔNG lặp lại các sự kiện đã có.\n\n"
        f"<context>{headings}</context>\n<text>\n{text}\n</text>"
    )


def _norm_label(label: str) -> str:
    return " ".join(label.split()).casefold()


def _dedup_key(e: AtomicEvent) -> tuple[str, str, str]:
    """Khoá nhận-dạng-trùng trong cùng unit: (label, mốc, địa điểm chính).

    KHÔNG chỉ theo label — hai sự kiện cùng nhãn nhưng khác mốc/nơi (vd 'Trận Đông
    Khê' ở hai thời điểm) là KHÁC nhau; completeness pass phải giữ cả hai. Trùng thật
    (cùng label+mốc+nơi) sẽ bị reconcile gộp sau bằng event_id."""
    loc0 = (e.locations[0] if e.locations else "").strip().casefold()
    return (_norm_label(e.label), (e.time_start or "").strip(), loc0)


def _merge_dedup(
    base: list[AtomicEvent], extra: list[AtomicEvent]
) -> list[AtomicEvent]:
    """Gộp event của completeness pass, bỏ trùng theo (label, mốc, địa điểm chính)."""
    seen = {_dedup_key(e) for e in base}
    merged = list(base)
    for e in extra:
        key = _dedup_key(e)
        if key[0] and key not in seen:  # key[0] = label đã chuẩn hoá, phải có
            seen.add(key)
            merged.append(e)
    return merged


def _parse_events(
    *,
    client: OpenAI,
    model: str,
    user_content: str,
) -> list[AtomicEvent]:
    """Một lượt gọi LLM Structured Outputs -> list AtomicEvent (rỗng nếu refusal)."""
    completion = client.chat.completions.parse(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        response_format=TimelineExtraction,
        timeout=60,
        temperature=0.0,  # ưu tiên độ chính xác; thà bỏ sót còn hơn bịa mốc/nơi
    )
    message = completion.choices[0].message
    if getattr(message, "refusal", None):
        log.warning("LLM từ chối (refusal) khi trích timeline -> trả rỗng cho lượt này.")
        return []
    parsed = message.parsed or _EMPTY
    return list(parsed.events)


def extract_timeline_events(
    text: str,
    heading_path: list[str] | None = None,
    *,
    client: OpenAI | None = None,
    model: str | None = None,
    unit_id: str | None = None,
) -> TimelineExtraction:
    """Trích atomic event cho một unit (đoạn gom theo heading).

    Raises:
        Exception: lỗi LLM không phục hồi được (CLI bắt và đếm vào lỗi).
    """
    if not text or not text.strip():
        return _EMPTY

    client = client or get_openai_client()
    settings = get_settings()
    # Như graph dùng `graph_llm_model`: timeline cũng cần model hỗ trợ strict Structured
    # Outputs (.parse) -> ưu tiên `timeline_llm_model`, fallback `llm_model`.
    model = model or settings.timeline_llm_model or settings.llm_model

    events = _parse_events(
        client=client,
        model=model,
        user_content=build_user_prompt(text, heading_path),
    )

    # Completeness pass cho unit lớn: hỏi lại phần bị sót.
    if len(text) > COMPLETENESS_CHAR_THRESHOLD:
        headings = " > ".join(heading_path) if heading_path else "(không có)"
        labels = "\n".join(f"- {e.label}" for e in events) or "(chưa có sự kiện nào)"
        extra = _parse_events(
            client=client,
            model=model,
            user_content=_completeness_prompt(labels, headings, text),
        )
        before = len(events)
        events = _merge_dedup(events, extra)
        if len(events) > before:
            prefix = f"[{unit_id}] " if unit_id else ""
            log.info(
                "%sCompleteness pass bổ sung %d sự kiện (đuôi context).",
                prefix,
                len(events) - before,
            )

    return TimelineExtraction(events=events)
