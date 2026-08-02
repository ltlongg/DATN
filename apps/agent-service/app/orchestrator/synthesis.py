"""Streaming structured-output cho synthesize — emit token thô, không batch/guardrails.

TẠM BỎ batching + guardrails hook (làm lại sau, xem `app/orchestrator/guardrails.py`).
Token nhả thẳng theo delta LLM trả về. `batch_chars` giữ trong signature để không phải
sửa call site ở `nodes.py`, hiện không dùng.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from openai import AsyncOpenAI
from pydantic_core import from_json

from app.core.llm import get_async_openai_client
from app.orchestrator.emitter import Emitter
from app.orchestrator.errors import SynthesisError
from app.schemas.ask import SynthesizedAnswer

# Nhả text TĨNH dần cho giống câu trả lời thường (hiệu ứng gõ). Cụm nhỏ ~chunk chars, cắt ở
# ranh giới từ; delay nhỏ giữa 2 cụm để client render tăng dần.
STATIC_STREAM_CHUNK_CHARS = 24
STATIC_STREAM_DELAY_SECONDS = 0.03


async def emit_text_as_batches(text: str, emitter: Emitter, batch_chars: int) -> None:
    """Stream một đoạn text tĩnh (honest/smalltalk) — emit nguyên khối, không guardrails."""
    if text:
        await emitter.emit("token", {"text": text})


async def stream_static_text(
    text: str,
    emitter: Emitter,
    *,
    chunk_chars: int = STATIC_STREAM_CHUNK_CHARS,
    delay: float = STATIC_STREAM_DELAY_SECONDS,
) -> None:
    """Nhả một đoạn text TĨNH dần theo từng cụm ~`chunk_chars` (cắt ở khoảng trắng gần nhất để
    không đứt giữa từ), sleep `delay` giữa các cụm -> hiển thị tăng dần như câu trả lời thường.
    Dùng cho safe message của guardrails. Ghép mọi cụm lại == `text` nguyên vẹn."""
    remaining = text
    while remaining:
        if len(remaining) <= chunk_chars:
            chunk, remaining = remaining, ""
        else:
            # Cắt ở khoảng trắng gần nhất <= chunk_chars (giữ khoảng trắng ở đầu cụm kế tiếp).
            cut = remaining.rfind(" ", 0, chunk_chars + 1)
            if cut <= 0:
                cut = chunk_chars
            chunk, remaining = remaining[:cut], remaining[cut:]
        await emitter.emit("token", {"text": chunk})
        if remaining and delay > 0:
            await asyncio.sleep(delay)


async def stream_synthesis(
    messages: list[dict[str, str]],
    *,
    emitter: Emitter,
    model: str,
    batch_chars: int,
    temperature: float = 0.0,
    client: AsyncOpenAI | None = None,
    on_usage: Callable[[int, int, int], Awaitable[None]] | None = None,
) -> SynthesizedAnswer:
    """Stream structured output `SynthesizedAnswer`; emit delta của `answer` THÔ (không
    batch/guardrails). Trả về SynthesizedAnswer cuối. `answer` là field đầu nên token ra
    trước, `used_chunk_ids`/`confidence` về ở cuối.

    `temperature` do admin chỉnh qua Cấu hình hệ thống (RuntimeConfig.llm_temperature); mặc
    định 0.0. `plan`/`resolve` GIỮ 0.0 cứng (cần deterministic), chỉ synthesize dùng field này.

    `on_usage(prompt, completion, total)` (nếu truyền) được await đúng 1 lần sau khi có
    usage. Mặc định None = giữ nguyên hành vi cũ (không đọc usage). `stream_options=
    include_usage` bật để response streaming có usage ở chunk cuối (VERIFY OpenAI SDK docs)."""
    client = client or get_async_openai_client()
    final: SynthesizedAnswer | None = None
    refusal: str | None = None
    prev_answer = ""

    async with client.chat.completions.stream(
        model=model,
        messages=messages,  # type: ignore[arg-type]
        response_format=SynthesizedAnswer,
        temperature=temperature,
        stream_options={"include_usage": True},
    ) as stream:
        async for event in stream:
            if event.type == "content.delta":
                # KHÔNG dùng event.parsed: partial-parse của SDK chỉ đưa field string vào
                # parsed khi chuỗi đã ĐÓNG nháy -> answer về 1 cục ở cuối, mất streaming.
                # Tự parse snapshot (JSON tích lũy thô) với allow_partial="trailing-strings"
                # để lấy được cả chuỗi answer đang dở dang.
                snapshot = getattr(event, "snapshot", None)
                if not snapshot:
                    continue
                try:
                    partial = from_json(snapshot, allow_partial="trailing-strings")
                except ValueError:
                    continue  # snapshot đứt giữa escape sequence -> chờ delta kế tiếp
                if isinstance(partial, dict):
                    cur = partial.get("answer")
                    if isinstance(cur, str) and len(cur) > len(prev_answer):
                        delta = cur[len(prev_answer):]
                        prev_answer = cur
                        await emitter.emit("token", {"text": delta})
            elif event.type == "content.done":
                final = event.parsed
            elif event.type == "refusal.done":
                refusal = event.refusal

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
