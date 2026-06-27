"""Reranker tùy chọn (cross-encoder) cho bước cuối của hybrid retrieval.

`reranker_model` rỗng -> no-op (giữ thứ tự RRF, `rerank_score` để None). Có model -> chấm
cặp `(question, chunk.text)` rồi sort giảm dần.

Nạp theo đúng model card AITeamVN/Vietnamese_Reranker: `AutoModelForSequenceClassification`
+ tokenizer (transformers thuần), KHÔNG dùng sentence-transformers CrossEncoder — vì
CrossEncoder mặc định `max_length=512` sẽ cắt cụt chunk dài, còn model này hỗ trợ tới 2304
token. `max_length` lấy từ `reranker_max_length`. Forward nặng CPU/GPU nên chạy trong
`asyncio.to_thread`. Không hardcode phụ thuộc một model; chỉ nạp khi config bật.
"""

from __future__ import annotations

import asyncio
from threading import Lock

from app.core.config import get_settings
from app.schemas.retrieval import RetrievedChunk

__all__ = ["rerank"]

_models: dict[str, object] = {}
_lock = Lock()


def _load(name: str):
    """Lazy-load + cache (tokenizer, model) theo tên model. eval() để tắt dropout."""
    cached = _models.get(name)
    if cached is None:
        with _lock:
            cached = _models.get(name)
            if cached is None:
                from transformers import (
                    AutoModelForSequenceClassification,
                    AutoTokenizer,
                )

                tokenizer = AutoTokenizer.from_pretrained(name)
                model = AutoModelForSequenceClassification.from_pretrained(name)
                model.eval()
                cached = (tokenizer, model)
                _models[name] = cached
    return cached


def _score(name: str, pairs: list[list[str]], max_length: int) -> list[float]:
    """Trả logit liên quan cho từng cặp [query, passage] (cao = liên quan hơn)."""
    import torch

    tokenizer, model = _load(name)
    inputs = tokenizer(
        pairs,
        padding=True,
        truncation=True,
        return_tensors="pt",
        max_length=max_length,
    )
    with torch.no_grad():
        logits = model(**inputs, return_dict=True).logits.view(-1).float()
    return logits.tolist()


async def rerank(question: str, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """Sort chunks theo độ liên quan cross-encoder. Rỗng model/chunks -> giữ nguyên."""
    settings = get_settings()
    if not settings.reranker_model or not chunks:
        return chunks

    pairs = [[question, chunk.text] for chunk in chunks]
    scores = await asyncio.to_thread(
        _score, settings.reranker_model, pairs, settings.reranker_max_length
    )
    for chunk, score in zip(chunks, scores):
        chunk.rerank_score = float(score)
    return sorted(chunks, key=lambda c: c.rerank_score or 0.0, reverse=True)
