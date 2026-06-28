"""Test batching token + guardrails hook + stream_synthesis (fake OpenAI stream).

Phủ: cắt batch ở dấu kết câu/ngưỡng ký tự, guardrails chặn -> blocked + raise, token ghép
lại == answer, lấy final qua content.done.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.orchestrator import guardrails
from app.orchestrator.emitter import ListEmitter
from app.orchestrator.errors import GuardrailsBlocked
from app.orchestrator.synthesis import (
    _find_cut,
    emit_text_as_batches,
    stream_synthesis,
)
from app.schemas.ask import SynthesizedAnswer


# --- _find_cut ---


def test_find_cut_sentence_end_before_threshold() -> None:
    assert _find_cut("Câu một. còn nữa", 160) == len("Câu một.")


def test_find_cut_threshold_before_sentence_end() -> None:
    # không có dấu kết câu trong 5 ký tự đầu -> cắt ở batch_chars
    assert _find_cut("abcdefghij", 5) == 5


def test_find_cut_waits_when_incomplete() -> None:
    assert _find_cut("chưa đủ", 160) is None


# --- emit_text_as_batches ---


async def test_emit_text_concatenates_to_original() -> None:
    emitter = ListEmitter()
    text = "Câu một. Câu hai. Câu ba."
    await emit_text_as_batches(text, emitter, 160)
    tokens = [d["text"] for t, d in emitter.events if t == "token"]
    assert "".join(tokens) == text
    assert len(tokens) == 3  # mỗi câu một batch


async def test_guardrails_block_emits_blocked_and_raises(monkeypatch) -> None:
    async def block_all(batch: str) -> bool:
        return False

    monkeypatch.setattr(guardrails, "check_batch", block_all)
    emitter = ListEmitter()
    with pytest.raises(GuardrailsBlocked):
        await emit_text_as_batches("Câu một. Câu hai.", emitter, 160)
    types = [t for t, _ in emitter.events]
    assert "blocked" in types
    assert "token" not in types  # batch đầu bị chặn -> không token nào emit


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


async def test_stream_synthesis_emits_answer_deltas_and_returns_final() -> None:
    final = SynthesizedAnswer(
        answer="Câu một. Câu hai.", used_chunk_ids=["c-1"], confidence="cao"
    )
    events = [
        SimpleNamespace(type="content.delta", parsed={"answer": "Câu "}),
        SimpleNamespace(type="content.delta", parsed={"answer": "Câu một."}),
        SimpleNamespace(type="content.delta", parsed={"answer": "Câu một. Câu hai."}),
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
    assert "".join(tokens) == "Câu một. Câu hai."
    assert result.used_chunk_ids == ["c-1"]
    assert result.confidence == "cao"
