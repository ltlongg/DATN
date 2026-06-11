"""Orchestrator chunking Level 2-4.

Pipeline cho mỗi Section (đã tách ở Level 1 trong `heading_parser`):
- Level 2-3: dùng **Chonkie `RecursiveChunker`** để gom theo paragraph ("\\n\\n") rồi
  line ("\\n") sao cho mỗi chunk ≤ chunk_size token. Chonkie CHỈ được cấu hình tới
  bậc "\\n" — không cho cắt nhỏ hơn (câu/từ).
- Level 4: nếu một khối vẫn vượt ngưỡng và không còn "\\n" để Chonkie tách →
  dùng **Chonkie `SlumberChunker`** (OpenAI-compatible LLM) để tách theo ngữ nghĩa.
  Lỗi/không cắt được → fallback `RecursiveChunker` xuống mức câu.

Mọi offset giữ tuyệt đối trên text gốc để citation chính xác.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

from app.core.config import Settings, get_settings
from app.indexing.chunk_slicer import ChunkSpan, build_chunk, build_line_starts
from app.indexing.heading_parser import parse_sections
from app.indexing.token_counter import count_tokens


@dataclass
class ChunkStats:
    """Số liệu quan sát quá trình chunking (để log/debug)."""

    sections: int = 0
    chunks: int = 0
    level4_calls: int = 0
    fallback_calls: int = 0
    llm_errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "sections": self.sections,
            "chunks": self.chunks,
            "level4_calls": self.level4_calls,
            "fallback_calls": self.fallback_calls,
            "llm_errors": list(self.llm_errors),
        }


def _chonkie_token_counter(text: str) -> int:
    """Wrapper để Chonkie đếm token qua count_tokens (tra cứu global lúc gọi -> test
    monkeypatch được, dù chunker bị cache)."""
    return count_tokens(text)


@lru_cache(maxsize=4)
def _section_chunker(max_tokens: int, min_chars: int):
    """RecursiveChunker chỉ gom tới bậc "\\n" (paragraph rồi line), đo bằng token VN."""
    from chonkie import RecursiveChunker
    from chonkie.types import RecursiveLevel, RecursiveRules

    rules = RecursiveRules(
        levels=[
            RecursiveLevel(delimiters=["\n\n"]),  # bậc 1: paragraph
            RecursiveLevel(delimiters=["\n"]),     # bậc 2: line (dừng ở đây)
        ]
    )
    return RecursiveChunker(
        tokenizer=_chonkie_token_counter,
        chunk_size=max_tokens,
        rules=rules,
        min_characters_per_chunk=min_chars,
    )


def _split_with_slumber(text: str, abs_start: int, max_tokens: int, settings: Settings) -> list[ChunkSpan]:
    """Dùng SlumberChunker (OpenAI-compatible) để tách khối quá khổ theo ngữ nghĩa.

    Trả [] nếu không cắt được (để fallback).
    """
    from chonkie import OpenAIGenie, SlumberChunker

    genie = OpenAIGenie(
        model=settings.llm_model,
        base_url=str(settings.openai_base_url) if settings.openai_base_url else None,
        api_key=settings.openai_api_key,
    )
    chunker = SlumberChunker(
        genie=genie,
        tokenizer=_chonkie_token_counter,  # đo bằng token VN, khớp phần còn lại của pipeline
        chunk_size=max_tokens,
        min_characters_per_chunk=settings.min_characters_per_chunk,
        verbose=False,
    )
    spans: list[ChunkSpan] = []
    for chunk in chunker(text):
        s = getattr(chunk, "start_index", None)
        e = getattr(chunk, "end_index", None)
        if s is None or e is None or not text[s:e].strip():
            continue
        spans.append(ChunkSpan(abs_start + s, abs_start + e))
    return spans if len(spans) > 1 else []


def _fallback_sentence_merge(text: str, abs_start: int, max_tokens: int, min_chars: int) -> list[ChunkSpan]:
    """Fallback khi LLM lỗi: Chonkie tách tới mức câu, không xuống từ/ký tự.

    Chonkie đã có cơ chế gom đoạn ngắn qua min_characters_per_chunk — chỉ cần
    cấu hình rules dừng ở câu thay vì default (xuống đến từ/ký tự).
    """
    from chonkie import RecursiveChunker
    from chonkie.types import RecursiveLevel, RecursiveRules

    rules = RecursiveRules(levels=[
        RecursiveLevel(delimiters=["\n\n"]),
        RecursiveLevel(delimiters=["\n"]),
        RecursiveLevel(delimiters=[". ", "! ", "? "]),
    ])
    chunker = RecursiveChunker(
        tokenizer=_chonkie_token_counter,
        chunk_size=max_tokens,
        rules=rules,
        min_characters_per_chunk=min_chars,
    )
    spans: list[ChunkSpan] = []
    for chunk in chunker(text):
        s = getattr(chunk, "start_index", None)
        e = getattr(chunk, "end_index", None)
        if s is None or e is None or not text[s:e].strip():
            continue
        spans.append(ChunkSpan(abs_start + s, abs_start + e))
    return spans or [ChunkSpan(abs_start, abs_start + len(text))]


def _chunk_slumber_or_fallback(
    text: str, abs_start: int, max_tokens: int, use_llm: bool, settings: Settings, stats: ChunkStats,
    *, verbose: bool = False,
) -> list[ChunkSpan]:
    if count_tokens(text) <= max_tokens:
        return [ChunkSpan(abs_start, abs_start + len(text))]
    if use_llm:
        stats.level4_calls += 1
        if verbose:
            print(f"  [L4-LLM] {count_tokens(text)} token -> SlumberChunker...", flush=True)
        try:
            spans = _split_with_slumber(text, abs_start, max_tokens, settings)
            if spans:
                if verbose:
                    print(f"    -> {len(spans)} spans", flush=True)
                return spans
        except Exception as exc:  # noqa: BLE001 - ghi nhận rồi fallback, không gãy pipeline
            stats.llm_errors.append(f"{type(exc).__name__}: {exc}")
            if verbose:
                print(f"    -> LỖI {type(exc).__name__}: {exc}", flush=True)
    stats.fallback_calls += 1
    if verbose:
        print(f"  [Fallback] sentence-merge ({count_tokens(text)} token)...", flush=True)
    return _fallback_sentence_merge(text, abs_start, max_tokens, settings.min_characters_per_chunk)


def _chunk_block(
    body: str, block_start: int, *, max_tokens: int, use_llm: bool, settings: Settings, stats: ChunkStats,
    verbose: bool = False,
) -> list[ChunkSpan]:
    """Cắt body của một section: Chonkie gom tới "\\n"; khối quá khổ -> Level 4."""
    chunker = _section_chunker(max_tokens, settings.min_characters_per_chunk)
    spans: list[ChunkSpan] = []
    for chunk in chunker(body):
        s, e = chunk.start_index, chunk.end_index
        if not body[s:e].strip():
            continue
        if count_tokens(body[s:e]) > max_tokens:
            # Khối Chonkie không tách thêm được bằng "\n" -> đẩy sang LLM/fallback.
            spans.extend(
                _chunk_slumber_or_fallback(
                    body[s:e], block_start + s, max_tokens, use_llm, settings, stats, verbose=verbose
                )
            )
        else:
            spans.append(ChunkSpan(block_start + s, block_start + e))
    return spans


def chunk_document(
    clean_text: str,
    *,
    use_llm: bool = True,
    document_title: str = "lichsu.md",
    source_file: str = "lichsu.clean.md",
    settings: Settings | None = None,
    verbose: bool = False,
) -> tuple[list[dict], ChunkStats]:
    """Chạy toàn bộ Level 1-4 trên `clean_text`, trả (chunks, stats).

    `clean_text` phải là nội dung ĐÃ preprocess (lichsu.clean.md) — offset citation
    tính trên chính chuỗi này.
    """
    settings = settings or get_settings()
    stats = ChunkStats()
    line_starts = build_line_starts(clean_text)
    sections = parse_sections(clean_text)
    stats.sections = len(sections)

    if verbose:
        print(f"Tìm thấy {len(sections)} section. Bắt đầu chunking...", flush=True)

    chunks: list[dict] = []
    index = 0
    _log_every = max(1, len(sections) // 20)  # in progress ~mỗi 5%
    for i, section in enumerate(sections):
        if verbose and (i == 0 or (i + 1) % _log_every == 0 or i == len(sections) - 1):
            heading = " > ".join(section.headings) if section.headings else "(root)"
            pct = (i + 1) * 100 // len(sections)
            print(f"  [{i+1:4d}/{len(sections)} {pct:3d}%] {heading[:70]}", flush=True)
        spans = _chunk_block(
            section.body,
            section.abs_start,
            max_tokens=settings.chunk_size,
            use_llm=use_llm,
            settings=settings,
            stats=stats,
            verbose=verbose,
        )
        for span in spans:
            span.headings = section.headings
            chunk = build_chunk(
                span,
                clean_text,
                line_starts,
                index,
                document_title=document_title,
                source_file=source_file,
            )
            if chunk is not None:
                chunks.append(chunk)
                index += 1

    stats.chunks = len(chunks)
    return chunks, stats
