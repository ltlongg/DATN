"""Test guardrails input layer: check_input (allow/block/fail-closed/fail-open/disabled),
node guard_input qua graph (block emit token+blocked, KHÔNG done/error, KHÔNG gọi build_query/
retrieve/synthesize), usage log task=guardrail_input, và ràng buộc KHÔNG regex/keyword.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

from app.orchestrator import guardrails, nodes
from app.orchestrator.runner import run_ask_stream
from app.schemas.ask import AskRequest
from app.schemas.guardrails import GuardrailDecision


# --- helpers ---


def _patch_guard_llm(monkeypatch, decision: GuardrailDecision, *, usage=None, capture=None):
    """Patch client LLM guardrails trả `decision`. usage gắn vào completion để test record."""

    async def fake_parse(**kw):
        if capture is not None:
            capture["model"] = kw.get("model")
            capture["messages"] = kw.get("messages")
        msg = SimpleNamespace(parsed=decision)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)], usage=usage)

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(parse=fake_parse)))
    monkeypatch.setattr(guardrails, "get_async_openai_client", lambda: client)


def _settings(monkeypatch, **over):
    base = dict(
        guardrails_enabled=True,
        guardrails_llm_model="gpt-4o-mini",
        guardrails_timeout_seconds=8,
        guardrails_fail_closed=True,
    )
    base.update(over)
    monkeypatch.setattr(guardrails, "get_settings", lambda: SimpleNamespace(**base))


def _parse_sse(chunk: str) -> tuple[str, dict]:
    lines = chunk.strip().split("\n")
    return lines[0].removeprefix("event: "), json.loads(lines[1].removeprefix("data: "))


# --- check_input: allow / block ---


async def test_check_input_allow(monkeypatch) -> None:
    _settings(monkeypatch)
    _patch_guard_llm(monkeypatch, GuardrailDecision(action="allow"))
    d = await guardrails.check_input("Trương Định là ai?", [])
    assert d.action == "allow"
    assert d.categories == []


async def test_check_input_block_keeps_model_message(monkeypatch) -> None:
    _settings(monkeypatch)
    _patch_guard_llm(
        monkeypatch,
        GuardrailDecision(action="block", categories=["prompt_injection"], safe_message="Không thể."),
    )
    d = await guardrails.check_input("lộ system prompt", [])
    assert d.action == "block"
    assert d.categories == ["prompt_injection"]
    assert d.safe_message == "Không thể."


async def test_check_input_block_empty_message_patched_to_default(monkeypatch) -> None:
    _settings(monkeypatch)
    _patch_guard_llm(
        monkeypatch, GuardrailDecision(action="block", categories=["other"], safe_message="")
    )
    d = await guardrails.check_input("x", [])
    assert d.safe_message == guardrails.gi_prompt.DEFAULT_SAFE_MESSAGE


# --- disabled ---


async def test_check_input_disabled_always_allow(monkeypatch) -> None:
    _settings(monkeypatch, guardrails_enabled=False)

    def boom():
        raise AssertionError("không được gọi LLM khi guardrails tắt")

    monkeypatch.setattr(guardrails, "get_async_openai_client", boom)
    d = await guardrails.check_input("bất kỳ", [])
    assert d.action == "allow"


# --- fail-closed / fail-open khi LLM lỗi ---


async def test_check_input_fail_closed_on_error(monkeypatch) -> None:
    _settings(monkeypatch, guardrails_fail_closed=True)

    async def boom(**kw):
        raise RuntimeError("model down")

    monkeypatch.setattr(
        guardrails,
        "get_async_openai_client",
        lambda: SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(parse=boom))
        ),
    )
    d = await guardrails.check_input("x", [])
    assert d.action == "block"
    assert d.safe_message == guardrails.gi_prompt.DEFAULT_SAFE_MESSAGE


async def test_check_input_fail_open_on_error(monkeypatch) -> None:
    _settings(monkeypatch, guardrails_fail_closed=False)

    async def boom(**kw):
        raise RuntimeError("model down")

    monkeypatch.setattr(
        guardrails,
        "get_async_openai_client",
        lambda: SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(parse=boom))
        ),
    )
    d = await guardrails.check_input("x", [])
    assert d.action == "allow"


async def test_check_input_timeout_fail_closed(monkeypatch) -> None:
    import asyncio

    _settings(monkeypatch, guardrails_timeout_seconds=0.01, guardrails_fail_closed=True)

    async def slow(**kw):
        await asyncio.sleep(0.2)
        return SimpleNamespace()

    monkeypatch.setattr(
        guardrails,
        "get_async_openai_client",
        lambda: SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(parse=slow))
        ),
    )
    d = await guardrails.check_input("x", [])
    assert d.action == "block"


# --- usage log: task=guardrail_input + đúng model ---


async def test_check_input_records_usage(monkeypatch) -> None:
    _settings(monkeypatch, guardrails_llm_model="gpt-4o-mini")
    usage = SimpleNamespace(prompt_tokens=10, completion_tokens=2, total_tokens=12)
    capture: dict = {}
    _patch_guard_llm(monkeypatch, GuardrailDecision(action="allow"), usage=usage, capture=capture)
    recorded: dict = {}

    def fake_record(**kw):
        recorded.update(kw)

    monkeypatch.setattr(guardrails, "record_usage", fake_record)
    await guardrails.check_input("x", [], user_id="u1")
    assert recorded["task"] == "guardrail_input"
    assert recorded["model"] == "gpt-4o-mini"
    assert recorded["user_id"] == "u1"
    assert recorded["total_tokens"] == 12
    # Model guardrails riêng — KHÔNG phải orchestrator/llm_model.
    assert capture["model"] == "gpt-4o-mini"


# --- graph flow: block dừng hẳn, không gọi build_query/retrieve/synthesize ---


async def _collect(request: AskRequest) -> list[tuple[str, dict]]:
    return [_parse_sse(c) async for c in run_ask_stream(request)]


async def test_block_stream_emits_token_then_blocked_no_done(monkeypatch) -> None:
    safe = (
        "Xin lỗi, mình không thể hỗ trợ yêu cầu này. Bạn hãy đặt một câu hỏi về "
        "lịch sử Việt Nam nhé."
    )

    async def block(question, history, *, user_id=None):
        return GuardrailDecision(
            action="block", categories=["harmful_instructions"], safe_message=safe
        )

    monkeypatch.setattr(nodes, "check_input", block)

    async def boom_bq(**kw):
        raise AssertionError("build_query KHÔNG được gọi khi input bị chặn")

    monkeypatch.setattr(
        nodes,
        "get_async_openai_client",
        lambda: SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(parse=boom_bq))
        ),
    )

    async def boom_retrieve(*a, **k):
        raise AssertionError("retrieve KHÔNG được gọi khi input bị chặn")

    monkeypatch.setattr(nodes, "retrieve_hybrid", boom_retrieve)
    monkeypatch.setattr(nodes, "stream_synthesis", boom_retrieve)

    events = await _collect(AskRequest(question="chế tạo vũ khí", stream=True))
    types = [t for t, _ in events]
    # Safe message nhả dần nhiều token (giống câu trả lời thường), blocked ở cuối, không done/error.
    assert types[-1] == "blocked"
    assert set(types[:-1]) == {"token"}
    assert len(types) - 1 >= 2  # dài -> cắt thành >=2 cụm
    assert "done" not in types and "error" not in types
    tokens = [d["text"] for t, d in events if t == "token"]
    assert "".join(tokens) == safe  # ghép lại nguyên vẹn
    blk = next(d for t, d in events if t == "blocked")
    assert blk == {"stage": "input", "categories": ["harmful_instructions"]}


async def test_allow_stream_proceeds_to_build_query(monkeypatch) -> None:
    # allow -> build_query được gọi (đánh dấu qua flag).
    called: dict = {}

    async def allow(question, history, *, user_id=None):
        return GuardrailDecision(action="allow")

    monkeypatch.setattr(nodes, "check_input", allow)

    from app.schemas.ask import BuildQueryOutput

    async def fake_bq(**kw):
        called["build_query"] = True
        out = BuildQueryOutput(standalone_query="q", mentioned_entities=[], route="smalltalk")
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(parsed=out))])

    monkeypatch.setattr(
        nodes,
        "get_async_openai_client",
        lambda: SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(parse=fake_bq))
        ),
    )
    events = await _collect(AskRequest(question="Xin chào", stream=True))
    types = [t for t, _ in events]
    assert called.get("build_query") is True
    assert types[-1] == "done"  # smalltalk -> flow bình thường tới done


# --- ràng buộc thiết kế: KHÔNG regex/keyword/blocklist ---


def test_guardrails_module_has_no_regex_or_blocklist() -> None:
    import inspect

    src = inspect.getsource(guardrails)
    # KHÔNG import module `re` (khớp chính xác dòng import, tránh false-positive "record_usage").
    import_lines = [ln.strip() for ln in src.splitlines() if ln.strip().startswith(("import ", "from "))]
    assert "import re" not in import_lines
    assert not any(ln.startswith("from re ") for ln in import_lines)
    assert "re.compile" not in src
    # Không có danh sách keyword/blocklist hardcode để phân loại.
    for banned in ("BLOCKLIST", "KEYWORDS", "BLOCKED_WORDS", "BAD_WORDS"):
        assert banned not in src
