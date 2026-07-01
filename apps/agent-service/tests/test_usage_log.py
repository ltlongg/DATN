"""Test instrument token usage online: record_usage (fake connect), build_query gọi
record_usage đúng khi completion có usage / bỏ qua khi không có, stream_synthesis gọi
on_usage.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.core import usage_log
from app.orchestrator import nodes
from app.orchestrator.emitter import ListEmitter
from app.orchestrator.synthesis import stream_synthesis
from app.schemas.ask import BuildQueryOutput, SynthesizedAnswer


# --- record_usage -----------------------------------------------------------


class _FakeCursor:
    def __init__(self, log):
        self._log = log

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self._log.append((sql, params))


class _FakeConn:
    def __init__(self, log):
        self._log = log

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def cursor(self):
        return _FakeCursor(self._log)

    def commit(self):
        pass


def test_record_usage_inserts_correct_columns(monkeypatch) -> None:
    log: list = []
    monkeypatch.setattr(usage_log.psycopg, "connect", lambda *a, **k: _FakeConn(log))
    usage_log.record_usage("build_query", "gpt", 10, 5, 15, user_id="u-1")
    insert = next(e for e in log if "INSERT INTO llm_usage" in e[0])
    _id, task, model, prompt, completion, total, user_id = insert[1]
    assert (task, model, prompt, completion, total, user_id) == (
        "build_query", "gpt", 10, 5, 15, "u-1",
    )


def test_record_usage_swallows_errors(monkeypatch) -> None:
    def boom(*a, **k):
        raise RuntimeError("db down")

    monkeypatch.setattr(usage_log.psycopg, "connect", boom)
    # Không raise -> ghi usage lỗi không làm fail answer.
    usage_log.record_usage("synthesize", "m", 1, 2, 3)


# --- build_query ghi usage --------------------------------------------------


def _client_returning(completion):
    async def fake_parse(**kw):
        return completion

    return SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(parse=fake_parse))
    )


def _parsed():
    return BuildQueryOutput(standalone_query="q", mentioned_entities=[], route="needs_retrieval")


async def test_build_query_records_usage_when_present(monkeypatch) -> None:
    usage = SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    completion = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(parsed=_parsed()))], usage=usage
    )
    monkeypatch.setattr(nodes, "get_async_openai_client", lambda: _client_returning(completion))
    captured: dict = {}
    monkeypatch.setattr(nodes, "record_usage", lambda **kw: captured.update(kw))

    await nodes.build_query({"question": "q", "history": [], "user_id": "u-1"}, {})
    assert captured["task"] == "build_query"
    assert (captured["prompt_tokens"], captured["completion_tokens"], captured["total_tokens"]) == (
        10, 5, 15,
    )
    assert captured["user_id"] == "u-1"


async def test_build_query_skips_usage_when_absent(monkeypatch) -> None:
    # completion KHÔNG có attribute usage (như mock cũ) -> không gọi record_usage.
    completion = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(parsed=_parsed()))]
    )
    monkeypatch.setattr(nodes, "get_async_openai_client", lambda: _client_returning(completion))
    called: list = []
    monkeypatch.setattr(nodes, "record_usage", lambda **kw: called.append(kw))

    await nodes.build_query({"question": "q", "history": [], "user_id": "u-1"}, {})
    assert called == []


# --- stream_synthesis on_usage ----------------------------------------------


class _FakeStream:
    def __init__(self, events, final_completion):
        self._events = events
        self._final_completion = final_completion

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
        return self._final_completion


class _FakeClient:
    def __init__(self, stream):
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(stream=lambda **kw: stream)
        )


async def test_stream_synthesis_calls_on_usage() -> None:
    final = SynthesizedAnswer(answer="A.", used_chunk_ids=["c"], confidence="cao")
    usage = SimpleNamespace(prompt_tokens=7, completion_tokens=3, total_tokens=10)
    completion = SimpleNamespace(
        usage=usage, choices=[SimpleNamespace(message=SimpleNamespace(parsed=final))]
    )
    events = [SimpleNamespace(type="content.done", parsed=final)]
    got: list = []

    async def on_usage(p, c, t):
        got.append((p, c, t))

    await stream_synthesis(
        [{"role": "user", "content": "x"}],
        emitter=ListEmitter(),
        model="m",
        batch_chars=160,
        client=_FakeClient(_FakeStream(events, completion)),
        on_usage=on_usage,
    )
    assert got == [(7, 3, 10)]
