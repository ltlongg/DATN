"""Trích entity + quan hệ (có kiểu) từ một chunk bằng LLM, cho Neo4j.

Pass RIÊNG với pass metadata (times/actors/locations/events). Dùng OpenAI Structured
Outputs (strict) qua `.parse()` -> output bảo đảm khớp `GraphExtraction`. Hàm thuần
(chỉ I/O là LLM) để CLI gọi song song qua ThreadPoolExecutor.

Có bước validate: bỏ relation có source/target không nằm trong tập entity vừa trích
(LLM đôi khi tham chiếu entity chưa khai báo) -> tránh tạo node mồ côi khi MERGE Neo4j.
"""

from __future__ import annotations

import logging

from openai import OpenAI

from app.core.config import get_settings
from app.core.llm import get_openai_client
from app.prompts.graph_extract import (
    GRAPH_PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_user_prompt,
)
from app.schemas.graph import GraphExtraction

__all__ = ["GRAPH_PROMPT_VERSION", "extract_graph"]

log = logging.getLogger(__name__)

_EMPTY = GraphExtraction(entities=[], relations=[])

def _drop_orphan_relations(
    extraction: GraphExtraction, chunk_id: str | None = None
) -> GraphExtraction:
    """Bỏ relation có endpoint không khớp entity nào; log CHI TIẾT cái bị bỏ.

    Log gồm chunk_id (nếu có), cặp (source)-[keyword]->(target) và endpoint nào thiếu
    — để phân biệt "hệ quả/khái niệm trừu tượng bị cấm làm entity" (bỏ là đúng) với
    "alias lệch / LLM quên khai báo entity" (mất mát thật, cần xem lại prompt).
    """
    names = {e.name for e in extraction.entities}
    kept = [r for r in extraction.relations if r.source in names and r.target in names]
    dropped = [
        r for r in extraction.relations if r.source not in names or r.target not in names
    ]
    if dropped:
        prefix = f"[{chunk_id}] " if chunk_id else ""
        items = []
        for r in dropped:
            missing = [
                f"{label}='{value}'"
                for label, value in (("source", r.source), ("target", r.target))
                if value not in names
            ]
            items.append(
                f"({r.source})-[{r.keyword}]->({r.target}) | thiếu {', '.join(missing)}"
            )
        log.warning(
            "%sBỏ %d relation mồ côi: %s", prefix, len(dropped), " ;; ".join(items)
        )
    return GraphExtraction(entities=extraction.entities, relations=kept)

def extract_graph(
    text: str,
    headings: dict[str, str] | None = None,
    *,
    client: OpenAI | None = None,
    model: str | None = None,
    chunk_id: str | None = None,
) -> GraphExtraction:
    """Trích entity/quan hệ cho một chunk.

    Raises:
        Exception: lỗi LLM không phục hồi được (CLI bắt và đếm vào lỗi).
    """
    if not text or not text.strip():
        return _EMPTY

    client = client or get_openai_client()
    settings = get_settings()
    model = model or settings.graph_llm_model or settings.llm_model

    completion = client.chat.completions.parse(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(text, headings)},
        ],
        response_format=GraphExtraction,
        timeout = 60,
        temperature=0.0,  # ưu tiên độ chính xác, LLM có thể bỏ qua prompt hơn là bịa ra entity/rel không có thật
    )
    message = completion.choices[0].message
    if getattr(message, "refusal", None):
        return _EMPTY
    return _drop_orphan_relations(message.parsed or _EMPTY, chunk_id)
