"""Trích "atomic event" (when–where–what) cho một unit, trả kết quả THEO TỪNG CHUNK.

Dùng OpenAI Structured Outputs (strict) qua `.parse()` -> output bảo đảm khớp
`TimelineExtraction`. Hàm thuần (chỉ I/O là LLM) để CLI gọi song song qua
ThreadPoolExecutor, giống khung `entity_relation_extractor.py`.

MỘT unit = ĐÚNG MỘT request. LLM đọc trọn unit để có ngữ cảnh (suy năm, giải tham chiếu)
nhưng phải quy mỗi event về chunk chứa bằng chứng, qua marker `ref` -> ở đây ánh xạ ngược
`ref` sang `chunk_id` thật.

KHÔNG có kết quả một phần: thiếu/trùng/lạ `ref` (hoặc LLM refusal) -> ném
`TimelineExtractionError`, CLI đếm lỗi và trích lại cả unit ở lần chạy sau. Nhận một
phần rồi cache theo chunk sẽ làm những chunk vắng mặt mất event VĨNH VIỄN (resume coi
unit đã xong).
"""

from __future__ import annotations

from openai import OpenAI

from app.core.config import get_settings
from app.core.llm import get_openai_client
from app.prompts.timeline_extract import (
    TIMELINE_PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_user_prompt,
)
from app.schemas.timeline import AtomicEvent, TimelineExtraction

__all__ = [
    "TIMELINE_PROMPT_VERSION",
    "TimelineExtractionError",
    "extract_unit_events",
]

class TimelineExtractionError(RuntimeError):
    """Kết quả LLM không dùng được cho cả unit (refusal hoặc `chunk_ref` sai hợp đồng)."""

def extract_unit_events(
    chunks: list[tuple[str, str]],
    heading_path: list[str] | None = None,
    *,
    client: OpenAI | None = None,
    model: str | None = None,
) -> dict[str, list[AtomicEvent]]:
    """Trích atomic event cho một unit -> `{chunk_id: events}` phủ ĐỦ mọi chunk đầu vào.

    Args:
        chunks: các cặp `(chunk_id, text)` theo đúng thứ tự văn bản trong unit.
        heading_path: đường dẫn mục chung của unit (bối cảnh cho LLM).

    Returns:
        Dict theo đúng thứ tự `chunks`; chunk không có sự kiện -> danh sách rỗng.

    Raises:
        TimelineExtractionError: LLM từ chối, không parse được, hoặc `chunk_ref` trả về
            thiếu/trùng/lạ so với marker đã gửi.
        Exception: lỗi mạng/LLM khác (CLI bắt và đếm vào lỗi).
    """
    client = client or get_openai_client()
    if model is None:
        # Như graph dùng `graph_llm_model`: timeline cũng cần model hỗ trợ strict Structured
        # Outputs (.parse) -> ưu tiên `timeline_llm_model`, fallback `llm_model`.
        settings = get_settings()
        model = settings.timeline_llm_model or settings.llm_model

    # `ref` do ĐÂY sinh (1..N) và cũng do đây ánh xạ ngược -> một nguồn sự thật duy nhất.
    ref_to_chunk_id = {str(i): cid for i, (cid, _) in enumerate(chunks, start=1)}
    marked = [(str(i), text) for i, (_, text) in enumerate(chunks, start=1)]

    completion = client.chat.completions.parse(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(marked, heading_path)},
        ],
        response_format=TimelineExtraction,
        timeout=180,
        # temperature=0.0,  # ưu tiên độ chính xác; thà bỏ sót còn hơn bịa mốc/nơi
        reasoning_effort="low"
    )
    message = completion.choices[0].message
    if getattr(message, "refusal", None):
        raise TimelineExtractionError(f"LLM từ chối trích timeline: {message.refusal}")
    if message.parsed is None:
        raise TimelineExtractionError("LLM không trả về cấu trúc parse được.")

    return _map_to_chunks(message.parsed, ref_to_chunk_id)

def _map_to_chunks(
    parsed: TimelineExtraction, ref_to_chunk_id: dict[str, str]
) -> dict[str, list[AtomicEvent]]:
    """Validate hợp đồng `chunk_ref` rồi ánh xạ về `chunk_id` thật (giữ thứ tự unit)."""
    by_ref: dict[str, list[AtomicEvent]] = {}
    for result in parsed.chunk_results:
        ref = result.chunk_ref.strip()
        if ref not in ref_to_chunk_id:
            raise TimelineExtractionError(
                f"chunk_ref lạ {ref!r} (chỉ gửi {sorted(ref_to_chunk_id, key=int)})."
            )
        if ref in by_ref:
            raise TimelineExtractionError(f"chunk_ref {ref!r} bị trả trùng.")
        by_ref[ref] = list(result.events)

    missing = [ref for ref in ref_to_chunk_id if ref not in by_ref]
    if missing:
        raise TimelineExtractionError(
            f"thiếu kết quả cho {len(missing)}/{len(ref_to_chunk_id)} chunk_ref: {missing}."
        )

    return {chunk_id: by_ref[ref] for ref, chunk_id in ref_to_chunk_id.items()}
