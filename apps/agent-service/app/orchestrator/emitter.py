"""Emitter — kênh phát event của orchestrator (status/token/citations/...).

Cùng một node code chạy cả hai chế độ: stream=False dùng `ListEmitter`/`NullEmitter`
(bỏ qua hoặc gom event, response dựng từ state cuối), stream=True dùng `QueueEmitter`
(SSE generator drain queue). Emitter được truyền qua `config["configurable"]["emitter"]`
nên không cần nằm trong LangGraph state (tránh hẳn bug async custom-stream của LangGraph).
"""

from __future__ import annotations

import asyncio


class Emitter:
    """Interface phát event. `data` là dict JSON-serializable."""

    async def emit(self, event_type: str, data: dict[str, object]) -> None:  # pragma: no cover
        raise NotImplementedError


class NullEmitter(Emitter):
    """Bỏ qua mọi event — dùng khi không cần stream (mặc định an toàn nếu thiếu emitter)."""

    async def emit(self, event_type: str, data: dict[str, object]) -> None:
        return None


class ListEmitter(Emitter):
    """Gom event vào list — tiện cho test và cho đường stream=False kiểm tra thứ tự."""

    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, object]]] = []

    async def emit(self, event_type: str, data: dict[str, object]) -> None:
        self.events.append((event_type, data))


class QueueEmitter(Emitter):
    """Đẩy event vào asyncio.Queue cho SSE generator tiêu thụ song song với graph chạy."""

    def __init__(self) -> None:
        self.queue: asyncio.Queue[tuple[str, dict[str, object]]] = asyncio.Queue()

    async def emit(self, event_type: str, data: dict[str, object]) -> None:
        await self.queue.put((event_type, data))
