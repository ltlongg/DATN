"""Extract metadata nội dung cho từng chunk (times/actors/locations/events).

Tách khỏi `indexing/` cấp trên vì đây là phase SAU chunking: đọc
`dataset/chunks_llm.json` (đã có metadata nền) rồi điền 4 trường nội dung.

Toàn bộ 4 trường (kể cả times, đã chuẩn hóa ISO) do LLM trích trong
`entity_extractor` qua OpenAI Structured Outputs (json_schema strict) — xem prompt
`prompts/metadata_extract`.
"""

from __future__ import annotations
