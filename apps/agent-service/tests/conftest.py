"""Cấu hình chung cho test: đảm bảo `app` import được khi chạy pytest."""

from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

_APP_ROOT = Path(__file__).resolve().parents[1]  # apps/agent-service
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))


@pytest.fixture(autouse=True)
def _isolate_prompt_store(monkeypatch: pytest.MonkeyPatch):
    """Giữ test hermetic (không chạm Postgres remote): chặn DB của prompt_store -> get_active_
    prompt luôn trả fallback = hằng SYSTEM_PROMPT trong code (đúng hành vi cũ trước Item 2).
    Xoá cache mỗi test. test_prompt_store tự setattr `connection` lại nên vẫn test logic thật."""
    from app.tools.prompts import prompt_store

    prompt_store.clear_cache()

    @contextmanager
    def _no_db(database_url: str | None = None):
        raise RuntimeError("prompt DB disabled in tests")
        yield  # pragma: no cover

    monkeypatch.setattr(prompt_store, "connection", _no_db)
    yield
    prompt_store.clear_cache()
