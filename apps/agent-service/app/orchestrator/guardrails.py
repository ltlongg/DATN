"""Guardrails input layer (v1) — 1 lớp kiểm câu hỏi TRƯỚC khi vào build_query.

`check_input` gọi LLM guardrails (model riêng `guardrails_llm_model`, KHÔNG fallback sang
orchestrator/llm_model) với Structured Output `GuardrailDecision`. Quyết định allow/block
HOÀN TOÀN do LLM — KHÔNG regex/keyword/blocklist (đây là ràng buộc thiết kế, xem plan).

Fail-closed: model lỗi/timeout + `guardrails_fail_closed=True` -> trả block + safe message
mặc định. `guardrails_enabled=False` -> luôn allow (bỏ qua LLM). Node `guard_input`
(orchestrator/nodes.py) tiêu thụ quyết định: allow -> đi tiếp; block -> emit token+blocked +
raise GuardrailsBlocked.

Xem `docs/plan/guardrails-input-plan.md`.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.core.config import get_settings
from app.core.llm import get_async_openai_client
from app.core.usage_log import record_usage
from app.prompts import guardrails_input as gi_prompt
from app.tools.prompts.prompt_store import get_active_prompt
from app.schemas.ask import ChatMessage
from app.schemas.guardrails import GuardrailDecision

logger = logging.getLogger("agent.guardrails")

GUARDRAIL_USAGE_TASK = "guardrail_input"


def _fail_closed_decision() -> GuardrailDecision:
    """Quyết định khi model lỗi/timeout với fail_closed=True: chặn + safe message mặc định."""
    return GuardrailDecision(
        action="block",
        categories=["other"],
        safe_message=gi_prompt.DEFAULT_SAFE_MESSAGE,
    )


async def _record_usage(
    completion: Any,
    model: str,
    user_id: str | None,
    conversation_id: str | None,
    message_id: str | None,
) -> None:
    usage = getattr(completion, "usage", None)
    if usage is None:
        return
    await asyncio.to_thread(
        record_usage,
        task=GUARDRAIL_USAGE_TASK,
        model=model,
        prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
        completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
        total_tokens=getattr(usage, "total_tokens", 0) or 0,
        user_id=user_id,
        conversation_id=conversation_id,
        message_id=message_id,
    )


async def _call_llm(
    question: str, history: list[ChatMessage], model: str
) -> tuple[GuardrailDecision, Any]:
    client = get_async_openai_client()
    completion = await client.chat.completions.parse(
        model=model,
        messages=[
            {
                "role": "system",
                "content": get_active_prompt(
                    "guardrails_input", fallback=gi_prompt.SYSTEM_PROMPT
                ),
            },
            {"role": "user", "content": gi_prompt.build_user_prompt(question, history)},
        ],
        response_format=GuardrailDecision,
        temperature=0.0,
    )
    parsed = completion.choices[0].message.parsed
    if parsed is None:
        raise ValueError("guardrails trả parsed None")
    return parsed, completion


async def check_input(
    question: str,
    history: list[ChatMessage],
    *,
    user_id: str | None = None,
    conversation_id: str | None = None,
    message_id: str | None = None,
) -> GuardrailDecision:
    """Kiểm 1 câu hỏi -> GuardrailDecision. Không bao giờ raise: lỗi/timeout được nuốt và
    quy về fail-closed (block) hoặc fail-open (allow) theo `guardrails_fail_closed`.

    Ghi usage `task="guardrail_input"` với `guardrails_llm_model` (record_usage tự nuốt lỗi).
    """
    settings = get_settings()
    if not settings.guardrails_enabled:
        return GuardrailDecision(action="allow")

    model = settings.guardrails_llm_model
    try:
        decision, completion = await asyncio.wait_for(
            _call_llm(question, history, model),
            timeout=settings.guardrails_timeout_seconds,
        )
    except Exception as exc:  # noqa: BLE001 — lỗi/timeout guardrails không được làm sập flow
        logger.warning(
            "guardrails check_input lỗi (%s) -> %s",
            type(exc).__name__,
            "fail-closed (block)" if settings.guardrails_fail_closed else "fail-open (allow)",
        )
        return _fail_closed_decision() if settings.guardrails_fail_closed else GuardrailDecision(
            action="allow"
        )

    await _record_usage(completion, model, user_id, conversation_id, message_id)
    # Model chặn nhưng quên safe_message -> vá bằng mặc định để luôn có gì đó stream cho user.
    if decision.action == "block" and not decision.safe_message.strip():
        decision.safe_message = gi_prompt.DEFAULT_SAFE_MESSAGE
    return decision
