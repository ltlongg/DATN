"""Test chunk_slicer — cắt vật lý + metadata nền."""

from __future__ import annotations

import pytest

from app.indexing import chunk_slicer
from app.indexing.chunk_slicer import ChunkSpan, build_chunk, build_line_starts


@pytest.fixture(autouse=True)
def _stub_token_counter(monkeypatch):
    # Thay tokenizer HF bằng đếm từ để test không phải tải model.
    monkeypatch.setattr(chunk_slicer, "count_tokens", lambda t: len(t.split()))


def test_build_line_starts():
    text = "a\nbb\n\nccc"
    assert build_line_starts(text) == [0, 2, 5, 6]


def test_line_number_mapping():
    text = "a\nbb\n\nccc"
    starts = build_line_starts(text)
    # 'a' ở dòng 1, 'bb' dòng 2, 'ccc' bắt đầu ở index 6 -> dòng 4.
    assert chunk_slicer._line_number(starts, 0) == 1
    assert chunk_slicer._line_number(starts, 2) == 2
    assert chunk_slicer._line_number(starts, 6) == 4


def test_strip_adjusts_offsets_so_text_matches_slice():
    clean = "# H\n\n  Câu văn có khoảng trắng thừa.  \n\nphần khác"
    raw_start = clean.index("  Câu")
    raw_end = clean.index("\n\nphần")
    span = ChunkSpan(raw_start, raw_end, headings={"h1": "H"})
    line_starts = build_line_starts(clean)

    chunk = build_chunk(span, clean, line_starts, 0)

    assert chunk is not None
    md = chunk["metadata"]
    # Text đã strip và offset vẫn khớp tuyệt đối.
    assert chunk["text"] == "Câu văn có khoảng trắng thừa."
    assert clean[md["start_index"] : md["end_index"]] == chunk["text"]


def test_embedding_text_format():
    clean = "x" * 10 + "Nội dung chunk."
    span = ChunkSpan(10, len(clean), headings={"h1": "Nhật thuộc", "h2": "Trận Lạng Sơn"})
    chunk = build_chunk(span, clean, build_line_starts(clean), 7, document_title="lichsu.md")

    assert chunk["chunk_id"] == "lichsu_clean-000007"
    assert chunk["embedding_text"] == (
        "Tiêu đề tài liệu: lichsu.md\n"
        "H1: Nhật thuộc\n"
        "H2: Trận Lạng Sơn\n\n"
        "Nội dung chunk."
    )


def test_whitespace_only_span_returns_none():
    clean = "abc\n\n   \n\ndef"
    span = ChunkSpan(3, 10, headings={})
    assert build_chunk(span, clean, build_line_starts(clean), 0) is None


def test_token_counts_present():
    clean = "Một hai ba bốn năm."
    span = ChunkSpan(0, len(clean), headings={"h1": "H"})
    chunk = build_chunk(span, clean, build_line_starts(clean), 0)
    md = chunk["metadata"]
    assert md["text_token_count"] == 5  # 5 từ
    assert md["embedding_token_count"] > md["text_token_count"]  # +header context
