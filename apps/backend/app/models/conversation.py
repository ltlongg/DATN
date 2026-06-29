"""Data access cho `conversations` + `messages` — psycopg trực tiếp.

Mọi function SYNC (mở connection riêng); API/service layer gọi qua anyio.to_thread.
Khóa nối agent-service là `chunk_id` nằm trong citations/visualization (JSONB) — backend
chỉ lưu nguyên, không diễn giải.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

from app.core.db import connection


class Conversation(BaseModel):
    id: str
    user_id: str
    title: str
    created_at: datetime
    updated_at: datetime


class Message(BaseModel):
    id: str
    conversation_id: str
    role: str  # "user" | "assistant"
    content: str
    clarification_needed: bool = False
    citations: list[dict[str, Any]] = Field(default_factory=list)
    visualization: dict[str, Any] | None = None
    retrieval_mode: str = "none"
    confidence: str | None = None
    warnings: list[Any] = Field(default_factory=list)
    created_at: datetime


def _to_conversation(row: dict[str, Any]) -> Conversation:
    return Conversation(
        id=str(row["id"]),
        user_id=str(row["user_id"]),
        title=row["title"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _to_message(row: dict[str, Any]) -> Message:
    return Message(
        id=str(row["id"]),
        conversation_id=str(row["conversation_id"]),
        role=row["role"],
        content=row["content"],
        clarification_needed=row["clarification_needed"],
        citations=row["citations"] or [],
        visualization=row["visualization"],
        retrieval_mode=row["retrieval_mode"],
        confidence=row["confidence"],
        warnings=row["warnings"] or [],
        created_at=row["created_at"],
    )


_CONV_COLS = "id, user_id, title, created_at, updated_at"
_MSG_COLS = (
    "id, conversation_id, role, content, clarification_needed, citations, "
    "visualization, retrieval_mode, confidence, warnings, created_at"
)


# --- conversations ---


def create_conversation(user_id: str, title: str) -> Conversation:
    conv_id = str(uuid.uuid4())
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"INSERT INTO conversations (id, user_id, title) VALUES (%s, %s, %s) "
            f"RETURNING {_CONV_COLS}",
            (conv_id, user_id, title),
        )
        row = cur.fetchone()
        conn.commit()
    assert row is not None
    return _to_conversation(row)


def list_conversations(user_id: str) -> list[Conversation]:
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT {_CONV_COLS} FROM conversations WHERE user_id = %s "
            f"ORDER BY updated_at DESC",
            (user_id,),
        )
        rows = cur.fetchall()
    return [_to_conversation(r) for r in rows]


def get_conversation(conversation_id: str) -> Conversation | None:
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT {_CONV_COLS} FROM conversations WHERE id = %s", (conversation_id,)
        )
        row = cur.fetchone()
    return _to_conversation(row) if row else None


def update_title(conversation_id: str, title: str) -> None:
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE conversations SET title = %s, updated_at = now() WHERE id = %s",
            (title, conversation_id),
        )
        conn.commit()


def touch_conversation(conversation_id: str) -> None:
    """Bump updated_at để conversation vừa hoạt động nổi lên đầu danh sách."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE conversations SET updated_at = now() WHERE id = %s", (conversation_id,)
        )
        conn.commit()


# --- messages ---


def add_message(
    conversation_id: str,
    role: str,
    content: str,
    *,
    message_id: str | None = None,
    clarification_needed: bool = False,
    citations: list[dict[str, Any]] | None = None,
    visualization: dict[str, Any] | None = None,
    retrieval_mode: str = "none",
    confidence: str | None = None,
    warnings: list[Any] | None = None,
) -> Message:
    msg_id = message_id or str(uuid.uuid4())
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"INSERT INTO messages (id, conversation_id, role, content, "
            f"clarification_needed, citations, visualization, retrieval_mode, "
            f"confidence, warnings) "
            f"VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING {_MSG_COLS}",
            (
                msg_id,
                conversation_id,
                role,
                content,
                clarification_needed,
                Jsonb(citations or []),
                Jsonb(visualization) if visualization is not None else None,
                retrieval_mode,
                confidence,
                Jsonb(warnings or []),
            ),
        )
        row = cur.fetchone()
        conn.commit()
    assert row is not None
    return _to_message(row)


def list_messages(conversation_id: str) -> list[Message]:
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT {_MSG_COLS} FROM messages WHERE conversation_id = %s "
            f"ORDER BY created_at ASC, id ASC",
            (conversation_id,),
        )
        rows = cur.fetchall()
    return [_to_message(r) for r in rows]


def count_messages(conversation_id: str) -> int:
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) AS n FROM messages WHERE conversation_id = %s",
            (conversation_id,),
        )
        row = cur.fetchone()
    return int(row["n"]) if row else 0
