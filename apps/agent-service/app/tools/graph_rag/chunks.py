"""Chuẩn hóa chunk dataset trước khi đưa vào Postgres + Qdrant + Neo4j.

`chunk_id` là khóa nối duy nhất xuyên hệ thống: Postgres PK ↔ Qdrant payload ↔
Neo4j `source_chunk_ids`. Không dùng khóa hash riêng.
"""

from __future__ import annotations

import re
from typing import Any

CHUNK_VECTOR_META_FIELDS: set[str] = {
    "chunk_id",
    "heading_path",
    "events",
    "actors",
    "times",
    "locations",
}

_HEADING_KEY_RE = re.compile(r"^h(\d+)$", re.IGNORECASE)


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value:
        text = _string_or_none(item)
        if text:
            items.append(text)
    return items


def build_heading_path(metadata: dict[str, Any]) -> list[str]:
    """Trả heading path theo thứ tự h1..hN, bỏ cấp thiếu/rỗng."""
    headings = metadata.get("headings")
    if not isinstance(headings, dict):
        return []

    ordered: list[tuple[int, str]] = []
    for key, value in headings.items():
        match = _HEADING_KEY_RE.match(str(key))
        text = _string_or_none(value)
        if match and text:
            ordered.append((int(match.group(1)), text))

    return [text for _, text in sorted(ordered, key=lambda item: item[0])]


def prepare_chunk_record(raw: dict[str, Any]) -> dict[str, Any]:
    """Chuẩn hóa một item từ `chunks_llm.json`.

    Lưu nguyên chunk (`text`/`embedding_text`/`metadata`) như file gốc, chỉ thêm
    `heading_path` rút từ metadata; `chunk_id` là khóa nối duy nhất. Các trường
    `events/actors/times/locations` được tách ra cho Qdrant payload (không cho Postgres).
    """
    metadata = raw.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}

    chunk_id = _string_or_none(raw.get("chunk_id"))
    if not chunk_id:
        raise ValueError("Chunk thiếu `chunk_id`.")

    text = raw.get("text")
    if not isinstance(text, str) or not text.strip():
        raise ValueError(f"Chunk {chunk_id} thiếu `text`.")

    embedding_text = raw.get("embedding_text")
    if not isinstance(embedding_text, str) or not embedding_text.strip():
        embedding_text = text

    return {
        "chunk_id": chunk_id,
        "text": text,
        "embedding_text": embedding_text,
        "metadata": metadata,
        "heading_path": build_heading_path(metadata),
        "events": _string_list(metadata.get("events")),
        "actors": _string_list(metadata.get("actors")),
        "times": _string_list(metadata.get("times")),
        "locations": _string_list(metadata.get("locations")),
    }


def prepare_chunk_records(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [prepare_chunk_record(chunk) for chunk in chunks]
