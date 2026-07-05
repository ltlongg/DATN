"""Item 2 — prompt_store runtime loader: get_active_prompt (production / fallback / nuốt lỗi),
cache TTL, seed idempotent. Dùng fake connection (không cần DB thật)."""

from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from app.tools.prompts import prompt_store


class _Cur:
    def __init__(self, row, log):
        self._row = row
        self._log = log

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        self._log.append((sql, params))

    def fetchone(self):
        return self._row


class _Conn:
    def __init__(self, row, log):
        self._row = row
        self._log = log

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def cursor(self):
        return _Cur(self._row, self._log)

    def commit(self):
        pass


def _patch_conn(monkeypatch, row, log=None):
    log = log if log is not None else []

    @contextmanager
    def fake_connection(database_url=None):
        yield _Conn(row, log)

    monkeypatch.setattr(prompt_store, "connection", fake_connection)
    return log


@pytest.fixture(autouse=True)
def _clear_cache():
    prompt_store.clear_cache()
    yield
    prompt_store.clear_cache()


def test_get_active_prompt_returns_production_content(monkeypatch) -> None:
    _patch_conn(monkeypatch, {"content": "PROD PROMPT"})
    assert prompt_store.get_active_prompt("build_query", fallback="CODE") == "PROD PROMPT"


def test_get_active_prompt_fallback_when_no_production(monkeypatch) -> None:
    _patch_conn(monkeypatch, None)  # không có version production
    assert prompt_store.get_active_prompt("synthesize", fallback="CODE") == "CODE"


def test_get_active_prompt_fallback_on_db_error(monkeypatch) -> None:
    @contextmanager
    def boom(database_url=None):
        raise RuntimeError("db down")
        yield  # pragma: no cover

    monkeypatch.setattr(prompt_store, "connection", boom)
    # Nuốt lỗi -> fallback, KHÔNG raise (answer flow không vỡ).
    assert prompt_store.get_active_prompt("guardrails_input", fallback="CODE") == "CODE"


def test_get_active_prompt_caches_within_ttl(monkeypatch) -> None:
    log = _patch_conn(monkeypatch, {"content": "PROD"})
    prompt_store.get_active_prompt("build_query", fallback="CODE")
    prompt_store.get_active_prompt("build_query", fallback="CODE")
    # Chỉ 1 lần chạm DB (SELECT) dù gọi 2 lần -> cache hoạt động.
    selects = [e for e in log if "SELECT content" in e[0]]
    assert len(selects) == 1


def test_seed_prompt_creates_when_absent(monkeypatch) -> None:
    log = _patch_conn(monkeypatch, None)  # SELECT 1 -> None (chưa có key)
    created = prompt_store.seed_prompt("build_query", "ONLINE", "T", "d", "CONTENT")
    assert created is True
    assert any("INSERT INTO managed_prompts" in e[0] for e in log)
    assert any("INSERT INTO prompt_versions" in e[0] for e in log)


def test_seed_prompt_idempotent_when_exists(monkeypatch) -> None:
    log = _patch_conn(monkeypatch, {"?column?": 1})  # SELECT 1 -> có row -> đã tồn tại
    created = prompt_store.seed_prompt("build_query", "ONLINE", "T", "d", "CONTENT")
    assert created is False
    assert not any("INSERT INTO" in e[0] for e in log)


# --- wiring: build_query dùng get_active_prompt (key + fallback đúng) --------


async def test_build_query_wires_get_active_prompt(monkeypatch) -> None:
    from app.orchestrator import nodes
    from app.prompts import build_query as bq_prompt
    from app.schemas.ask import BuildQueryOutput

    captured: dict = {}

    def fake_get_active_prompt(key, *, fallback):
        captured["key"] = key
        captured["fallback"] = fallback
        return "USED PROMPT"

    monkeypatch.setattr(nodes, "get_active_prompt", fake_get_active_prompt)

    parsed = BuildQueryOutput(standalone_query="q", mentioned_entities=[], route="smalltalk")
    completion = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(parsed=parsed))])

    async def fake_parse(**kw):
        captured["messages"] = kw["messages"]
        return completion

    monkeypatch.setattr(
        nodes,
        "get_async_openai_client",
        lambda: SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(parse=fake_parse))
        ),
    )

    await nodes.build_query({"question": "q", "history": []}, {})
    assert captured["key"] == "build_query"
    assert captured["fallback"] == bq_prompt.SYSTEM_PROMPT
    # system message thực sự dùng content trả về từ get_active_prompt
    assert captured["messages"][0]["content"] == "USED PROMPT"
