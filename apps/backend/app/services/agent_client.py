"""HTTP client tới agent-service — CHỈ chế độ streaming (backend không expose non-stream).

Hai thời điểm lỗi (backend-plan.md "Agent Client / Error mapping"):
- TRƯỚC khi stream mở (connect/status): còn đổi được HTTP status -> ném AppError, endpoint
  trả 503/504/502, StreamingResponse CHƯA bắt đầu.
- SAU khi stream mở: HTTP đã 200, mọi lỗi đi qua event SSE. Lỗi nghiệp vụ tới dưới dạng
  event `error`/`blocked` (proxy nguyên); idle timeout (httpx.ReadTimeout) -> client tự
  phát một event `error` backend_stream_failed.

Timeout: KHÔNG giới hạn tổng thời gian (câu dài là bình thường). Chỉ chặn connect và
idle giữa 2 lần có dữ liệu (httpx `read` reset mỗi lần nhận byte -> chính là idle timeout).
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.errors import AppError

logger = logging.getLogger("backend.agent_client")


class AgentAskRequest(BaseModel):
    """Contract BACKEND -> AGENT (`/ask`). Khớp `AskRequest` của agent-service."""

    question: str = Field(min_length=1, max_length=4000)
    history: list[dict[str, str]] = Field(default_factory=list, max_length=12)
    stream: bool = True
    debug: bool = False


@dataclass(frozen=True)
class SseEvent:
    event: str
    data: dict[str, object]


def format_sse(event: str, data: dict[str, object]) -> str:
    """Đóng gói 1 event SSE đúng format agent-service dùng (ensure_ascii=False -> giữ
    nguyên tiếng Việt, không đổi nội dung token)."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _parse_sse(lines: AsyncIterator[str]) -> AsyncIterator[SseEvent]:
    """Parse dòng SSE -> SseEvent. Mỗi event = các dòng `event:`/`data:` tới dòng trống.
    Nhiều dòng data nối bằng \\n (theo spec). Bỏ event không có data hợp lệ."""
    event_type = "message"
    data_lines: list[str] = []

    async for raw_line in lines:
        line = raw_line.rstrip("\r")
        if line == "":  # hết một event
            if data_lines:
                payload = "\n".join(data_lines)
                try:
                    data = json.loads(payload)
                except json.JSONDecodeError:
                    logger.warning("SSE data không parse được JSON: %r", payload[:200])
                    data = {}
                yield SseEvent(event=event_type, data=data)
            event_type = "message"
            data_lines = []
            continue
        if line.startswith(":"):  # comment / keep-alive
            continue
        if line.startswith("event:"):
            event_type = line[len("event:") :].strip()
        elif line.startswith("data:"):
            data_lines.append(line[len("data:") :].lstrip())


class AgentStream:
    """Stream đã mở (HTTP 200). `events()` drain tới hết rồi tự đóng client/response."""

    def __init__(self, client: httpx.AsyncClient, response: httpx.Response) -> None:
        self._client = client
        self._response = response

    async def events(self) -> AsyncIterator[SseEvent]:
        try:
            async for event in _parse_sse(self._response.aiter_lines()):
                yield event
        except httpx.TimeoutException:
            # Idle timeout (>read) hoặc treo giữa stream — HTTP đã 200, báo qua event.
            logger.warning("agent stream idle/timeout — phát event error backend_stream_failed")
            yield SseEvent(
                event="error",
                data={"code": "backend_stream_failed", "message": "Luồng trả lời bị gián đoạn."},
            )
        except httpx.HTTPError as exc:
            logger.warning("agent stream lỗi transport: %s", type(exc).__name__)
            yield SseEvent(
                event="error",
                data={"code": "backend_stream_failed", "message": "Luồng trả lời bị gián đoạn."},
            )
        finally:
            await self.aclose()

    async def aclose(self) -> None:
        await self._response.aclose()
        await self._client.aclose()


async def open_ask_stream(request: AgentAskRequest) -> AgentStream:
    """Mở kết nối + kiểm HTTP status TRƯỚC khi trả stream. Lỗi ở bước này còn map được
    HTTP status (endpoint chưa mở StreamingResponse). Trả AgentStream nếu agent trả 200."""
    settings = get_settings()
    timeout = httpx.Timeout(
        connect=settings.agent_connect_timeout_seconds,
        read=settings.agent_read_idle_timeout_seconds,
        write=settings.agent_connect_timeout_seconds,
        pool=settings.agent_connect_timeout_seconds,
    )
    client = httpx.AsyncClient(timeout=timeout, base_url=settings.agent_service_url)
    req = client.build_request("POST", "/ask", json=request.model_dump())

    try:
        response = await client.send(req, stream=True)
    except httpx.ConnectTimeout:
        await client.aclose()
        raise AppError(504, "agent_timeout", "Dịch vụ trả lời không phản hồi kịp.")
    except httpx.HTTPError:
        # ConnectError, ref-used, DNS... — agent process không bắt máy.
        await client.aclose()
        raise AppError(503, "agent_unavailable", "Dịch vụ trả lời đang tạm thời không sẵn sàng.")

    if response.status_code != 200:
        body = await response.aread()
        await response.aclose()
        await client.aclose()
        logger.warning(
            "agent /ask trả status %s (mong đợi 200): %s",
            response.status_code,
            body[:500].decode("utf-8", "replace"),
        )
        # 422 = backend gửi sai contract; mọi non-200 khác ở đường stream cũng là lỗi
        # phía agent/contract -> 502 (xem plan: agent không trả 503/504 cho stream).
        raise AppError(502, "agent_bad_response", "Dịch vụ trả lời phản hồi không hợp lệ.")

    return AgentStream(client, response)
