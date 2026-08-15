"""Cắt vật lý ChunkSpan thành chunk hoàn chỉnh + metadata nền.

Nhận một `ChunkSpan` (khoảng [abs_start, abs_end) trên text gốc) và sinh ra dict
chunk đúng schema trong `docs/plan/chunking-embedding-plan.md`:
- `text`: nội dung đã strip (offset được điều chỉnh để vẫn khớp tuyệt đối).
- `embedding_text`: context heading + text.
- vị trí citation: start/end index (ký tự) và start/end line (dòng, 1-based).
- token count cho cả `text` và `embedding_text`.

Metadata nội dung (events/actors/times/locations) để rỗng — extract ở phase sau.
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass, field
from typing import Any

from app.indexing.token_counter import count_tokens

@dataclass
class ChunkSpan:
    """Một khoảng văn bản sẽ trở thành 1 chunk.

    abs_start/abs_end là offset ký tự (tuyệt đối) trên text gốc; headings là chuỗi
    heading cha kế thừa từ Section.
    """

    abs_start: int
    abs_end: int
    headings: dict[str, str] = field(default_factory=dict)

def build_line_starts(text: str) -> list[int]:
    """Precompute offset ký tự bắt đầu của mỗi dòng (để map index -> số dòng).

    Trả về list tăng dần, phần tử đầu luôn là 0. Dùng chung cho toàn tài liệu, chỉ
    tính 1 lần.
    """
    starts = [0]
    idx = text.find("\n")
    while idx != -1:
        starts.append(idx + 1)
        idx = text.find("\n", idx + 1)
    return starts

def _line_number(line_starts: list[int], index: int) -> int:
    """Số dòng (1-based) chứa ký tự tại `index`."""
    return bisect.bisect_right(line_starts, index)

def _build_embedding_text(headings: dict[str, str], document_title: str, text: str) -> str:
    header = [f"Tiêu đề tài liệu: {document_title}"]
    for key in sorted(headings, key=lambda k: int(k[1:])):
        header.append(f"{key.upper()}: {headings[key]}")
    return "\n".join(header) + "\n\n" + text

def build_chunk(
    span: ChunkSpan,
    clean_text: str,
    line_starts: list[int],
    chunk_index: int,
    *,
    document_title: str = "lichsu.md",
    source_file: str = "lichsu.clean.md",
    chunk_id_prefix: str = "lichsu_clean",
) -> dict[str, Any] | None:
    """Sinh dict chunk từ một ChunkSpan. Trả None nếu span chỉ chứa whitespace."""

    raw = clean_text[span.abs_start : span.abs_end]
    stripped = raw.strip()
    if not stripped:
        return None

    # Điều chỉnh offset sau khi strip để text vẫn khớp clean_text[start:end].
    leading = len(raw) - len(raw.lstrip())
    start = span.abs_start + leading
    end = start + len(stripped)
    text = clean_text[start:end]

    embedding_text = _build_embedding_text(span.headings, document_title, text)

    return {
        "chunk_id": f"{chunk_id_prefix}-{chunk_index:06d}",
        "text": text,
        "embedding_text": embedding_text,
        "metadata": {
            "document_title": document_title,
            "headings": dict(span.headings),
            "events": [],
            "actors": [],
            "times": [],
            "locations": [],
            "source_file": source_file,
            "chunk_index": chunk_index,
            "start_line": _line_number(line_starts, start),
            "end_line": _line_number(line_starts, end - 1),
            "start_index": start,
            "end_index": end,
            "text_token_count": count_tokens(text),
            "embedding_token_count": count_tokens(embedding_text),
        },
    }
