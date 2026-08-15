"""Test reranker optional (AutoModelForSequenceClassification, theo model card
AITeamVN/Vietnamese_Reranker): rỗng model -> no-op; có model -> chấm logit cặp
(query, text) rồi sort giảm dần. Mock `_score` để khỏi nạp torch/transformers thật.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.core import reranker as RR
from app.schemas.retrieval import RetrievedChunk

def _chunk(chunk_id, text):
    return RetrievedChunk(chunk_id=chunk_id, text=text, metadata={}, heading_path=[])

async def test_reranker_can_be_disabled(monkeypatch) -> None:
    monkeypatch.setattr(
        RR, "get_settings", lambda: SimpleNamespace(reranker_model="", reranker_max_length=512)
    )

    def fail_score(*a, **k):
        raise AssertionError("không được nạp model khi reranker tắt")

    monkeypatch.setattr(RR, "_score", fail_score)
    chunks = [_chunk("c-1", "a"), _chunk("c-2", "b")]
    out = await RR.rerank("q", chunks)
    assert [c.chunk_id for c in out] == ["c-1", "c-2"]  # giữ nguyên
    assert all(c.rerank_score is None for c in out)

async def test_reranker_reorders_chunks_when_enabled_with_mock(monkeypatch) -> None:
    monkeypatch.setattr(
        RR,
        "get_settings",
        lambda: SimpleNamespace(
            reranker_model="fake-model", reranker_max_length=2304, rerank_batch_size=8
        ),
    )

    captured = {}

    def fake_score(name, pairs, max_length, batch_size):
        captured["name"] = name
        captured["pairs"] = pairs
        captured["max_length"] = max_length
        captured["batch_size"] = batch_size
        return [0.1, 0.9]  # c-1 thấp, c-2 cao -> đảo thứ tự

    monkeypatch.setattr(RR, "_score", fake_score)
    chunks = [_chunk("c-1", "a"), _chunk("c-2", "b")]
    out = await RR.rerank("q", chunks)

    assert [c.chunk_id for c in out] == ["c-2", "c-1"]  # sort theo logit desc
    assert out[0].rerank_score == 0.9
    # cặp (query, text) + max_length truyền đúng theo model card.
    assert captured["pairs"] == [["q", "a"], ["q", "b"]]
    assert captured["max_length"] == 2304
    assert captured["batch_size"] == 8

async def test_reranker_noop_when_no_chunks(monkeypatch) -> None:
    monkeypatch.setattr(
        RR,
        "get_settings",
        lambda: SimpleNamespace(
            reranker_model="fake-model", reranker_max_length=512, rerank_batch_size=8
        ),
    )
    monkeypatch.setattr(RR, "_score", lambda *a, **k: (_ for _ in ()).throw(AssertionError))
    assert await RR.rerank("q", []) == []

# --- chia batch + nối tiếp GPU (2026-07-31) ---

class _FakeBatch(dict):
    """Giả `BatchEncoding`: `.to(device)` trả chính nó, `**` unpack được vào model."""

    def to(self, _device):
        return self

class _FakeLogits:
    def __init__(self, values):
        self._values = values

    def view(self, *_a):
        return self

    def float(self):
        return self

    def tolist(self):
        return self._values

class _FakeOutput:
    def __init__(self, values):
        self.logits = _FakeLogits(values)

def _patch_fake_model(monkeypatch, on_batch=None):
    """Thay `_load` bằng cặp tokenizer/model giả — không nạp torch weights thật."""

    def tokenizer(pairs, **_kw):
        if on_batch is not None:
            on_batch(pairs)
        return _FakeBatch(input_ids=[p[1] for p in pairs])

    def model(**kw):
        return _FakeOutput([float(x) for x in kw["input_ids"]])

    monkeypatch.setattr(RR, "_load", lambda _name: (tokenizer, model, "cpu"))

def test_score_splits_into_batches_and_keeps_input_order(monkeypatch) -> None:
    """Đỉnh VRAM phải phụ thuộc `batch_size`, KHÔNG phụ thuộc số cặp truyền vào — đó là cả
    lý do tồn tại của tham số này (xem docstring reranker.py). Thứ tự phải giữ nguyên vì
    caller zip điểm với danh sách chunk."""
    sizes: list[int] = []
    _patch_fake_model(monkeypatch, on_batch=lambda pairs: sizes.append(len(pairs)))
    scores = RR._score("fake", [["q", i] for i in range(10)], 512, 4)
    assert sizes == [4, 4, 2]  # cắt đều, phần dư vẫn chạy
    assert scores == [float(i) for i in range(10)]

def test_score_with_batch_larger_than_input_runs_once(monkeypatch) -> None:
    sizes: list[int] = []
    _patch_fake_model(monkeypatch, on_batch=lambda pairs: sizes.append(len(pairs)))
    RR._score("fake", [["q", 0], ["q", 1]], 512, 8)
    assert sizes == [2]

def test_score_holds_the_gpu_lock_while_running(monkeypatch) -> None:
    """B1 chạy N query song song -> N lần `to_thread` cùng đòi VRAM. Không nối tiếp thì 2
    query đo được 270s thay vì 2×25s (thrash). Kiểm bằng cách thử giành semaphore ngay
    trong lúc forward đang chạy."""
    free_during_run: list[bool] = []

    def probe(_pairs):
        acquired = RR._gpu_lock.acquire(blocking=False)
        free_during_run.append(acquired)
        if acquired:
            RR._gpu_lock.release()

    _patch_fake_model(monkeypatch, on_batch=probe)
    RR._score("fake", [["q", 0]], 512, 8)
    assert free_during_run == [False]  # đang bị giữ -> query khác phải xếp hàng

def test_gpu_lock_is_released_even_when_forward_raises(monkeypatch) -> None:
    """Rerank hỏng một lần không được khoá chết mọi câu hỏi sau đó."""

    def tokenizer(_pairs, **_kw):
        raise RuntimeError("CUDA OOM")

    monkeypatch.setattr(RR, "_load", lambda _name: (tokenizer, None, "cpu"))
    try:
        RR._score("fake", [["q", 0]], 512, 8)
    except RuntimeError:
        pass
    assert RR._gpu_lock.acquire(blocking=False) is True
    RR._gpu_lock.release()
