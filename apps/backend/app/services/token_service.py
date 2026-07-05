"""Logic thuần (không I/O) gom usage rows -> token summary + breakdown theo message. Tách
thuần để unit-test không cần DB (cùng idiom cost_service.py/quality_service.py). Input rỗng
-> tổng hợp rỗng (dùng cho cả 'chưa có usage' lẫn 'bảng llm_usage chưa tồn tại').

Xem admin-restructure-plan.md §Item 3.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.schemas.logs import (
    ConversationTokens,
    MessageTokens,
    MessageTokenTaskRow,
    TokenOverall,
    TokenSummary,
)


def compute_token_summary(rows: list[dict[str, Any]]) -> TokenSummary:
    """rows = usage ĐÃ gắn conversation_id (cột: conversation_id, prompt/completion/total_tokens).
    `overall` = tổng toàn bộ rows; `by_conversation` = cộng dồn theo conversation_id."""
    total_calls = len(rows)
    total_prompt = sum(int(r.get("prompt_tokens") or 0) for r in rows)
    total_completion = sum(int(r.get("completion_tokens") or 0) for r in rows)
    total_tokens = sum(int(r.get("total_tokens") or 0) for r in rows)
    avg = (total_tokens / total_calls) if total_calls else 0.0

    calls: dict[str, int] = defaultdict(int)
    tokens: dict[str, int] = defaultdict(int)
    for r in rows:
        cid = str(r.get("conversation_id"))
        calls[cid] += 1
        tokens[cid] += int(r.get("total_tokens") or 0)

    by_conversation = [
        ConversationTokens(conversation_id=cid, call_count=calls[cid], total_tokens=tokens[cid])
        for cid in tokens
    ]
    return TokenSummary(
        overall=TokenOverall(
            total_calls=total_calls,
            total_prompt_tokens=total_prompt,
            total_completion_tokens=total_completion,
            total_tokens=total_tokens,
            avg_tokens_per_call=round(avg, 2),
        ),
        by_conversation=by_conversation,
    )


def build_message_tokens(rows: list[dict[str, Any]]) -> list[MessageTokens]:
    """rows = usage 1 hội thoại đã gộp theo (message_id, task, model). Gom lại theo message_id
    -> mỗi message có list dòng task + tổng token. Giữ thứ tự message_id xuất hiện trong rows."""
    grouped: dict[str, list[MessageTokenTaskRow]] = defaultdict(list)
    for r in rows:
        mid = str(r.get("message_id"))
        grouped[mid].append(
            MessageTokenTaskRow(
                task=str(r.get("task") or "unknown"),
                model=str(r.get("model") or ""),
                prompt_tokens=int(r.get("prompt_tokens") or 0),
                completion_tokens=int(r.get("completion_tokens") or 0),
                total_tokens=int(r.get("total_tokens") or 0),
            )
        )
    return [
        MessageTokens(
            message_id=mid,
            total_tokens=sum(t.total_tokens for t in task_rows),
            rows=task_rows,
        )
        for mid, task_rows in grouped.items()
    ]
