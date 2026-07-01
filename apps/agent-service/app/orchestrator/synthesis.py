"""Streaming structured-output cho synthesize + batching token qua guardrails hook.

Stream theo BATCH (cụm/câu), KHÔNG token thô: mỗi batch qua `guardrails.check_batch` TRƯỚC
khi emit `token`. Cùng cơ chế batch dùng lại cho honest_answer/direct_response (text tĩnh).
Xem `docs/plan/orchestrator-plan.md` §Streaming.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from openai import AsyncOpenAI

from app.core.llm import get_async_openai_client
from app.orchestrator import guardrails
from app.orchestrator.emitter import Emitter
from app.orchestrator.errors import GuardrailsBlocked, SynthesisError
from app.schemas.ask import SynthesizedAnswer

_SENTENCE_ENDERS = ".!?\n"


def _find_cut(text: str, batch_chars: int) -> int | None:
    """Chỉ số cắt batch (exclusive): dấu kết câu HOẶC đủ batch_chars — cái nào tới trước.
    Trả None nếu chưa đủ một batch."""
    first_end = next(
        (i + 1 for i, ch in enumerate(text) if ch in _SENTENCE_ENDERS), None
    )
    if first_end is not None and first_end <= batch_chars:
        return first_end
    if len(text) >= batch_chars:
        return batch_chars
    return None


async def _guard_and_emit(batch: str, emitter: Emitter) -> None:
    """Một batch qua guardrails hook rồi emit `token`. Hook chặn -> `blocked` + raise."""
    if not await guardrails.check_batch(batch):
        await emitter.emit("blocked", {"reason": "guardrails"})
        raise GuardrailsBlocked()
    await emitter.emit("token", {"text": batch})


async def _drain_batches(
    pending: str, emitter: Emitter, batch_chars: int, *, final: bool
) -> str:
    """Cắt & emit hết batch hoàn chỉnh trong `pending`. final=True flush phần còn lại."""
    while True:
        cut = _find_cut(pending, batch_chars)
        if cut is None:
            break
        batch, pending = pending[:cut], pending[cut:]
        await _guard_and_emit(batch, emitter)
    if final and pending:
        await _guard_and_emit(pending, emitter)
        pending = ""
    return pending


async def emit_text_as_batches(text: str, emitter: Emitter, batch_chars: int) -> None:
    """Stream một đoạn text tĩnh (honest/smalltalk) qua cùng cơ chế batch + guardrails."""
    await _drain_batches(text, emitter, batch_chars, final=True)


async def stream_synthesis(
    messages: list[dict[str, str]],
    *,
    emitter: Emitter,
    model: str,
    batch_chars: int,
    client: AsyncOpenAI | None = None,
    on_usage: Callable[[int, int, int], Awaitable[None]] | None = None,
) -> SynthesizedAnswer:
    """Stream structured output `SynthesizedAnswer`; emit delta của `answer` thành batch
    qua guardrails. Trả về SynthesizedAnswer cuối. `answer` là field đầu nên token ra
    trước, `used_chunk_ids`/`confidence` về ở cuối.

    `on_usage(prompt, completion, total)` (nếu truyền) được await đúng 1 lần sau khi có
    usage. Mặc định None = giữ nguyên hành vi cũ (không đọc usage). `stream_options=
    include_usage` bật để response streaming có usage ở chunk cuối (VERIFY OpenAI SDK docs)."""
    client = client or get_async_openai_client()
    final: SynthesizedAnswer | None = None
    refusal: str | None = None
    prev_answer = ""
    pending = ""

    async with client.chat.completions.stream(
        model=model,
        messages=messages,  # type: ignore[arg-type]
        response_format=SynthesizedAnswer,
        temperature=0.0,
        stream_options={"include_usage": True},
    ) as stream:
        async for event in stream:
            if event.type == "content.delta":
                parsed = event.parsed
                if isinstance(parsed, dict):
                    cur = parsed.get("answer")
                    if isinstance(cur, str) and len(cur) > len(prev_answer):
                        pending += cur[len(prev_answer):]
                        prev_answer = cur
                        pending = await _drain_batches(
                            pending, emitter, batch_chars, final=False
                        )
            elif event.type == "content.done":
                final = event.parsed
            elif event.type == "refusal.done":
                refusal = event.refusal
        await _drain_batches(pending, emitter, batch_chars, final=True)

    if refusal:
        raise SynthesisError("refusal")
    # Lấy completion cuối (đã tích lũy, không gọi API thêm) khi cần final fallback HOẶC usage.
    completion = None
    if final is None or on_usage is not None:
        completion = await stream.get_final_completion()
    if final is None and completion is not None:
        final = completion.choices[0].message.parsed
    if final is None:
        raise SynthesisError("empty_synthesis")
    if on_usage is not None and completion is not None:
        usage = getattr(completion, "usage", None)
        if usage is not None:
            await on_usage(
                usage.prompt_tokens, usage.completion_tokens, usage.total_tokens
            )
    return final
