"""Test emit_text_as_batches + stream_synthesis (fake OpenAI stream).

TẠM BỎ batching + guardrails (xem app/orchestrator/synthesis.py) — token nhả thô theo
delta LLM, không cắt câu. Phủ: text tĩnh emit nguyên khối, token ghép lại == answer, lấy
final qua content.done.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.orchestrator.emitter import ListEmitter
from app.orchestrator.synthesis import emit_text_as_batches, stream_synthesis
from app.schemas.ask import SynthesizedAnswer

# --- emit_text_as_batches ---


async def test_emit_text_as_one_token() -> None:
    emitter = ListEmitter()
    text = "Câu một. Câu hai. Câu ba."
    await emit_text_as_batches(text, emitter, 160)
    tokens = [d["text"] for t, d in emitter.events if t == "token"]
    assert tokens == [text]  # không batch -> nguyên khối 1 token


async def test_emit_text_empty_emits_nothing() -> None:
    emitter = ListEmitter()
    await emit_text_as_batches("", emitter, 160)
    assert emitter.events == []


# --- stream_synthesis với fake OpenAI stream ---


class _FakeStream:
    def __init__(self, events, final):
        self._events = events
        self._final = final

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def __aiter__(self):
        self._it = iter(self._events)
        return self

    async def __anext__(self):
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration

    async def get_final_completion(self):
        return self._final


class _FakeClient:
    def __init__(self, stream):
        completions = SimpleNamespace(stream=lambda **kw: stream)
        self.chat = SimpleNamespace(completions=completions)


async def test_stream_synthesis_emits_raw_deltas_and_returns_final() -> None:
    final = SynthesizedAnswer(
        answer="Câu một. Câu hai.", used_chunk_ids=["c-1"], confidence="cao"
    )
    # Mô phỏng SDK thật: parsed KHÔNG chứa answer khi chuỗi chưa đóng nháy (bug từng làm
    # mất streaming) -> code phải lấy từ snapshot (JSON tích lũy thô, dở dang).
    events = [
        SimpleNamespace(type="content.delta", parsed={}, snapshot='{"answer": "Câu '),
        SimpleNamespace(type="content.delta", parsed={}, snapshot='{"answer": "Câu một.'),
        SimpleNamespace(
            type="content.delta", parsed={}, snapshot='{"answer": "Câu một. Câu hai.'
        ),
        SimpleNamespace(type="content.done", parsed=final),
    ]
    emitter = ListEmitter()
    result = await stream_synthesis(
        [{"role": "user", "content": "x"}],
        emitter=emitter,
        model="m",
        batch_chars=160,
        client=_FakeClient(_FakeStream(events, None)),
    )
    tokens = [d["text"] for t, d in emitter.events if t == "token"]
    # nhả thô theo từng delta, KHÔNG gộp theo câu -> 3 token khớp 3 event delta
    assert tokens == ["Câu ", "một.", " Câu hai."]
    assert "".join(tokens) == "Câu một. Câu hai."
    assert result.used_chunk_ids == ["c-1"]
    assert result.confidence == "cao"
