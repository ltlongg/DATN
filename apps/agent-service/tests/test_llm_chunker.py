"""Test orchestrator Level 2-4 — llm_chunker (Chonkie gom \\n\\n/\\n, LLM cho khối quá khổ)."""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.indexing import chunk_slicer, llm_chunker
from app.indexing.chunk_slicer import ChunkSpan
from app.indexing.llm_chunker import _chunk_block, chunk_document


@pytest.fixture(autouse=True)
def _stub_token_counter(monkeypatch):
    # Đếm token = đếm từ, áp cho cả hai module dùng count_tokens (Chonkie cũng đi qua đây).
    word_count = lambda t: len(t.split())  # noqa: E731
    monkeypatch.setattr(llm_chunker, "count_tokens", word_count)
    monkeypatch.setattr(chunk_slicer, "count_tokens", word_count)


@pytest.fixture
def settings() -> Settings:
    return Settings(chunk_size=4, min_characters_per_chunk=1, openai_api_key="")


# ----- Chonkie gom paragraph/line (Level 2-3) -----

def test_chonkie_packs_paragraphs(settings):
    block = "aa bb\n\ncc dd\n\nee ff"  # 3 paragraph, mỗi cái 2 từ, chunk_size=4
    spans = _chunk_block(block, 0, max_tokens=4, use_llm=False, settings=settings, stats=llm_chunker.ChunkStats())
    # Gom được "aa bb"+"cc dd" (=4) rồi tách "ee ff" -> 2 chunk; không có khối quá khổ.
    assert len(spans) == 2
    assert "cc dd" in block[spans[0].abs_start : spans[0].abs_end]
    assert block[spans[1].abs_start : spans[1].abs_end].strip() == "ee ff"


def test_chonkie_splits_paragraph_by_lines(settings):
    block = "l1 l1\nl2 l2\nl3 l3"  # 1 paragraph, 6 từ > 4, có "\n"
    stats = llm_chunker.ChunkStats()
    spans = _chunk_block(block, 0, max_tokens=4, use_llm=False, settings=settings, stats=stats)
    assert len(spans) == 2
    assert stats.level4_calls == 0  # tách được bằng "\n", không cần LLM


# ----- Level 4: khối quá khổ không có \n -----

def test_oversize_block_uses_slumber(settings, monkeypatch):
    block = "w1 w2 w3 w4 w5 w6"  # 6 từ, không có \n\n hay \n -> Chonkie bí -> Level 4

    def fake_slumber(text, abs_start, max_tokens, _settings):
        mid = text.index("w4")
        return [ChunkSpan(abs_start, abs_start + mid), ChunkSpan(abs_start + mid, abs_start + len(text))]

    monkeypatch.setattr(llm_chunker, "_split_with_slumber", fake_slumber)
    stats = llm_chunker.ChunkStats()
    spans = _chunk_block(block, 0, max_tokens=4, use_llm=True, settings=settings, stats=stats)

    assert stats.level4_calls == 1
    assert stats.fallback_calls == 0
    assert len(spans) == 2


def test_oversize_block_fallback_when_llm_fails(settings, monkeypatch):
    block = "w1 w2 w3 w4 w5 w6"

    def boom(*_args, **_kwargs):
        raise RuntimeError("LLM down")

    def fake_fallback(text, abs_start, max_tokens, min_chars):
        mid = len(text) // 2
        return [ChunkSpan(abs_start, abs_start + mid), ChunkSpan(abs_start + mid, abs_start + len(text))]

    monkeypatch.setattr(llm_chunker, "_split_with_slumber", boom)
    monkeypatch.setattr(llm_chunker, "_fallback_sentence_merge", fake_fallback)
    stats = llm_chunker.ChunkStats()
    spans = _chunk_block(block, 0, max_tokens=4, use_llm=True, settings=settings, stats=stats)

    assert stats.level4_calls == 1
    assert stats.fallback_calls == 1
    assert len(stats.llm_errors) == 1
    assert len(spans) == 2


def test_fallback_sentence_merge_groups_short_sentences(settings):
    """Chonkie phải gom câu ngắn lại cho đủ ngưỡng, không tạo chunk 1 câu riêng lẻ."""
    from app.indexing.llm_chunker import _fallback_sentence_merge

    # 4 câu, mỗi câu 2 từ. chunk_size=4 -> Chonkie nên gom 2 câu thành 1 chunk.
    text = "w1 w2. w3 w4. w5 w6. w7 w8."
    spans = _fallback_sentence_merge(text, 0, max_tokens=4, min_chars=1)

    assert len(spans) == 2, f"Mong 2 chunk (gom 2 câu/chunk), nhận {len(spans)}"
    for span in spans:
        chunk_text = text[span.abs_start:span.abs_end]
        assert chunk_text.strip(), "Chunk không được rỗng"


# ----- end-to-end document -----

def test_chunk_document_attaches_headings_and_offsets():
    big = Settings(chunk_size=100, min_characters_per_chunk=1, openai_api_key="")
    text = "# H1\n\naa bb cc\n\n## H2\n\ndd ee\n"
    chunks, stats = chunk_document(text, use_llm=False, settings=big)

    assert stats.chunks == 2
    assert chunks[0]["metadata"]["headings"] == {"h1": "H1"}
    assert chunks[0]["text"] == "aa bb cc"
    assert chunks[1]["metadata"]["headings"] == {"h1": "H1", "h2": "H2"}
    assert [c["metadata"]["chunk_index"] for c in chunks] == [0, 1]
    # Offset khớp tuyệt đối.
    for chunk in chunks:
        md = chunk["metadata"]
        assert text[md["start_index"] : md["end_index"]] == chunk["text"]
