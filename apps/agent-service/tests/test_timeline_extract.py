"""Test phần KHÔNG cần LLM của extractor: prompt an toàn brace + dedup completeness."""

from __future__ import annotations

from app.indexing.timeline.atomic_event_extractor import _merge_dedup
from app.prompts.timeline_extract import build_user_prompt
from app.schemas.timeline import AtomicEvent


def _ev(label: str, time_start: str = "", locations: list[str] | None = None) -> AtomicEvent:
    return AtomicEvent(
        label=label,
        summary="s",
        time_start=time_start,
        time_end="",
        locations=locations or [],
        parent_event="",
        confidence="cao",
    )


def test_build_user_prompt_an_toan_voi_dau_ngoac_nhon() -> None:
    # Regression: text chứa '{' '}' KHÔNG được làm vỡ prompt (trước đây str.format ném lỗi).
    text = "Mật mã {A} và tập {1, 2, 3} xuất hiện trong tài liệu."
    out = build_user_prompt(text, ["Thời kì thuộc địa", "Mục X"])
    assert text in out
    assert "Thời kì thuộc địa > Mục X" in out


def test_build_user_prompt_khong_heading() -> None:
    out = build_user_prompt("Đoạn văn.", None)
    assert "(không có)" in out and "Đoạn văn." in out


def test_merge_dedup_giu_event_cung_label_khac_moc() -> None:
    # Cùng label nhưng khác mốc -> là sự kiện KHÁC, phải giữ cả hai (recall).
    base = [_ev("Trận Đông Khê", "1950-09", ["Đông Khê"])]
    extra = [
        _ev("Trận Đông Khê", "1947-10", ["Đông Khê"]),  # khác mốc -> giữ
        _ev("Trận Đông Khê", "1950-09", ["Đông Khê"]),  # trùng hệt -> bỏ
    ]
    merged = _merge_dedup(base, extra)
    assert len(merged) == 2
    assert {e.time_start for e in merged} == {"1950-09", "1947-10"}


def test_merge_dedup_bo_event_khong_label() -> None:
    assert _merge_dedup([], [_ev("   ", "1950")]) == []
