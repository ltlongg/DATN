"""Reranker tùy chọn (cross-encoder) cho bước cuối của hybrid retrieval.

`reranker_model` rỗng -> no-op (giữ thứ tự RRF, `rerank_score` để None). Có model -> chấm
cặp `(question, chunk.text)` rồi sort giảm dần.

Nạp theo đúng model card AITeamVN/Vietnamese_Reranker: `AutoModelForSequenceClassification`
+ tokenizer (transformers thuần), KHÔNG dùng sentence-transformers CrossEncoder — vì
CrossEncoder mặc định `max_length=512` sẽ cắt cụt chunk dài, còn model này hỗ trợ tới 2304
token. `max_length` lấy từ `reranker_max_length`. Forward nặng CPU/GPU nên chạy trong
`asyncio.to_thread`. Không hardcode phụ thuộc một model; chỉ nạp khi config bật.

**Hai ràng buộc VRAM, cả hai đều đo được** (RTX 4060 Laptop 8.6 GB, 2026-07-31):

1. `_score` chia batch `rerank_batch_size` thay vì nhồi cả `hybrid_candidate_k` cặp vào MỘT
   forward. GPU này còn cõng cả model embedding tiếng Việt, nên phần trống thực tế nhỏ hơn
   nhiều con số 8.6 GB. Đo trên 27 cặp thật: batch 30 -> 25.3s (đỉnh 5.42 GB), batch 8 ->
   **2.26s** (đỉnh 4.82 GB). Chênh VRAM chỉ 0.6 GB mà nhanh gấp 11 lần — vượt phần trống là
   Windows đổ sang shared memory qua PCIe, chậm sập mặt. Không phải "batch to thì nhanh hơn".
2. `_GPU_LOCK` nối tiếp các lần rerank. Từ bậc B1, `retrieve` chạy N query SONG SONG
   (`asyncio.gather`) nên có N lần `to_thread` cùng đòi VRAM một lúc — 2 query đo được 270s
   thay vì 2×25s, tức không cộng tuyến tính mà thrash. Nối tiếp thì tổng vẫn là tổng.
"""

from __future__ import annotations

import asyncio
from threading import Lock, Semaphore

from app.core.config import get_settings
from app.schemas.retrieval import RetrievedChunk

__all__ = ["rerank"]

_models: dict[str, object] = {}
_lock = Lock()

# Nối tiếp mọi forward reranker. `asyncio.to_thread` đẩy `_score` sang thread pool, nên N
# query song song của một bước todo (B1) sẽ chạy đồng thời nếu không chặn. Semaphore chứ
# không phải Lock: cần nới lên >1 khi đổi sang card nhiều VRAM thì chỉ sửa một con số.
_GPU_SLOTS = 1
_gpu_lock = Semaphore(_GPU_SLOTS)


def _load(name: str):
    """Lazy-load + cache (tokenizer, model, device) theo tên model. eval() để tắt dropout;
    tự chuyển model sang GPU nếu `torch.cuda.is_available()`, fallback CPU."""
    cached = _models.get(name)
    if cached is None:
        with _lock:
            cached = _models.get(name)
            if cached is None:
                import torch
                from transformers import (
                    AutoModelForSequenceClassification,
                    AutoTokenizer,
                )

                device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
                tokenizer = AutoTokenizer.from_pretrained(name)
                model = AutoModelForSequenceClassification.from_pretrained(name)
                model.eval()
                model.to(device)
                cached = (tokenizer, model, device)
                _models[name] = cached
    return cached


def _score(
    name: str, pairs: list[list[str]], max_length: int, batch_size: int
) -> list[float]:
    """Trả logit liên quan cho từng cặp [query, passage] (cao = liên quan hơn).

    Chia batch để đỉnh VRAM không phụ thuộc số cặp truyền vào — xem docstring module. Giữ
    NGUYÊN thứ tự đầu vào: caller zip kết quả với `chunks`.
    """
    import torch

    tokenizer, model, device = _load(name)
    scores: list[float] = []
    with _gpu_lock:
        for start in range(0, len(pairs), batch_size):
            inputs = tokenizer(
                pairs[start : start + batch_size],
                padding=True,
                truncation=True,
                return_tensors="pt",
                max_length=max_length,
            ).to(device)
            with torch.no_grad():
                logits = model(**inputs, return_dict=True).logits.view(-1).float()
            scores.extend(logits.tolist())
    return scores


async def rerank(question: str, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """Sort chunks theo độ liên quan cross-encoder. Rỗng model/chunks -> giữ nguyên."""
    settings = get_settings()
    if not settings.reranker_model or not chunks:
        return chunks

    pairs = [[question, chunk.text] for chunk in chunks]
    scores = await asyncio.to_thread(
        _score,
        settings.reranker_model,
        pairs,
        settings.reranker_max_length,
        settings.rerank_batch_size,
    )
    for chunk, score in zip(chunks, scores):
        chunk.rerank_score = float(score)
    return sorted(chunks, key=lambda c: c.rerank_score or 0.0, reverse=True)
