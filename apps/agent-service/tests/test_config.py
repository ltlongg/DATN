"""Test ràng buộc của `Settings` — phần knob có luật kiến trúc, không phải mọi field.

Chỉ những knob mà đặt sai giá trị sẽ hỏng ÂM THẦM mới cần test ở đây.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_retrieval_max_steps_defaults_to_two() -> None:
    assert Settings().retrieval_max_steps == 2


def test_retrieval_max_steps_rejects_three() -> None:
    """Từ chối THẲNG chứ không im lặng kẹp xuống 2 (plan §8).

    Kiến trúc hiện tại chỉ an toàn ở 2 bước: validator cấm `resolve` ở bước cuối nên bước duy
    nhất được `resolve` là bước 1. Cho 3 bước thì bước 2 vừa có `resolve` vừa đứng sau một
    bước đã tích luỹ chunk — sai âm thầm. Ai chỉnh lên 3 phải biết mình chỉnh vào chỗ chưa hỗ trợ.
    """
    with pytest.raises(ValidationError):
        Settings(retrieval_max_steps=3)


def test_retrieval_max_steps_rejects_zero() -> None:
    with pytest.raises(ValidationError):
        Settings(retrieval_max_steps=0)
