"""Test phần KHÔNG cần LLM của extractor: render prompt theo marker + hợp đồng chunk_ref."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.indexing.timeline.atomic_event_extractor import (
    TimelineExtractionError,
    _map_to_chunks,
    extract_unit_events,
)
from app.prompts.timeline_extract import (
    SYSTEM_PROMPT,
    TIMELINE_PROMPT_VERSION,
    build_user_prompt,
)
from app.schemas.timeline import AtomicEvent, ChunkEvents, TimelineExtraction


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


def _parsed(*pairs: tuple[str, list[AtomicEvent]]) -> TimelineExtraction:
    return TimelineExtraction(
        chunk_results=[ChunkEvents(chunk_ref=ref, events=evs) for ref, evs in pairs]
    )


# --- build_user_prompt: marker phải rõ ràng và không vỡ vì nội dung ---------------


def test_timeline_prompt_dung_chung_cho_moi_giai_doan() -> None:
    assert TIMELINE_PROMPT_VERSION == "timeline-extract-unified-v4"
    assert len(SYSTEM_PROMPT) <= 13_000
    assert '"time_start": "179 TCN"' in SYSTEM_PROMPT
    assert '"time_start": "XII"' in SYSTEM_PROMPT
    assert '"time_start": "1954-03-13"' in SYSTEM_PROMPT
    assert "không quy thành năm 1150" in SYSTEM_PROMPT
    assert "cách ngày nay" in SYSTEM_PROMPT


def test_timeline_prompt_giu_su_kien_phat_hien_khao_co_co_moc_ro() -> None:
    assert '"label": "Phát hiện di vật khảo cổ tại Núi Đọ"' in SYSTEM_PROMPT
    assert '"time_start": "1960"' in SYSTEM_PROMPT
    assert '"locations": ["Núi Đọ"]' in SYSTEM_PROMPT
    assert "heading chỉ cung cấp ngữ cảnh, không phải bộ lọc thời đại" in SYSTEM_PROMPT


def test_build_user_prompt_gan_marker_ref_cho_tung_chunk() -> None:
    out = build_user_prompt([("1", "Đoạn A."), ("2", "Đoạn B.")], ["Phần I", "Mục X"])
    assert '<chunk ref="1">Đoạn A.</chunk>' in out
    assert '<chunk ref="2">Đoạn B.</chunk>' in out
    assert "<heading_context>Phần I > Mục X</heading_context>" in out
    assert out.index('ref="1"') < out.index('ref="2"')  # giữ thứ tự văn bản


def test_build_user_prompt_an_toan_voi_dau_ngoac_nhon() -> None:
    # Regression: text chứa '{' '}' KHÔNG được làm vỡ prompt (trước đây str.format ném lỗi).
    text = "Mật mã {A} và tập {1, 2, 3} xuất hiện trong tài liệu."
    out = build_user_prompt([("1", text)], ["Thời kì thuộc địa", "Mục X"])
    assert text in out


def test_build_user_prompt_khong_heading() -> None:
    out = build_user_prompt([("1", "Đoạn văn.")], None)
    assert "(không có)" in out and "Đoạn văn." in out


# --- _map_to_chunks: ánh xạ ref -> chunk_id thật + validate hợp đồng ---------------


def test_map_ref_ve_dung_chunk_id_that() -> None:
    refs = {"1": "c-000", "2": "c-001"}
    out = _map_to_chunks(_parsed(("1", [_ev("E1")]), ("2", [_ev("E2")])), refs)
    assert list(out) == ["c-000", "c-001"]  # giữ thứ tự unit
    assert [e.label for e in out["c-000"]] == ["E1"]
    assert [e.label for e in out["c-001"]] == ["E2"]


def test_chunk_khong_co_event_van_duoc_giu_voi_list_rong() -> None:
    refs = {"1": "c-000", "2": "c-001"}
    out = _map_to_chunks(_parsed(("1", [_ev("E1")]), ("2", [])), refs)
    assert out["c-001"] == []  # rỗng là kết quả HỢP LỆ, phải vào cache


def test_ref_tra_ve_khong_theo_thu_tu_van_map_dung() -> None:
    refs = {"1": "c-000", "2": "c-001"}
    out = _map_to_chunks(_parsed(("2", [_ev("E2")]), ("1", [_ev("E1")])), refs)
    assert [e.label for e in out["c-000"]] == ["E1"]
    assert list(out) == ["c-000", "c-001"]  # output vẫn theo thứ tự unit


def test_thieu_ref_lam_fail_toan_unit() -> None:
    refs = {"1": "c-000", "2": "c-001", "3": "c-002"}
    with pytest.raises(TimelineExtractionError, match="thiếu kết quả"):
        _map_to_chunks(_parsed(("1", [_ev("E1")]), ("2", [])), refs)


def test_trung_ref_lam_fail_toan_unit() -> None:
    refs = {"1": "c-000", "2": "c-001"}
    with pytest.raises(TimelineExtractionError, match="trùng"):
        _map_to_chunks(_parsed(("1", [_ev("E1")]), ("1", [_ev("E2")]), ("2", [])), refs)


def test_ref_la_lam_fail_toan_unit() -> None:
    refs = {"1": "c-000"}
    with pytest.raises(TimelineExtractionError, match="lạ"):
        _map_to_chunks(_parsed(("1", []), ("9", [_ev("E9")])), refs)


# --- extract_unit_events: khớp ref giữa prompt gửi đi và bảng ánh xạ ngược ---------


def _stub_client(
    parsed: TimelineExtraction | None = None, refusal: str | None = None
) -> tuple[Any, dict[str, Any]]:
    """Client giả trả sẵn kết quả + ghi lại tham số đã gửi (không gọi mạng)."""
    captured: dict[str, Any] = {}

    def parse(**kwargs: Any) -> Any:
        captured.update(kwargs)
        message = SimpleNamespace(refusal=refusal, parsed=parsed)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(parse=parse))
    )
    return client, captured


def test_ref_trong_prompt_khop_bang_anh_xa_nguoc() -> None:
    """Bug im lặng nguy hiểm nhất: prompt đánh ref kiểu này, map ngược lại kiểu khác."""
    client, captured = _stub_client(_parsed(("1", [_ev("E1")]), ("2", [])))
    out = extract_unit_events(
        [("c-aaa", "Đoạn A."), ("c-bbb", "Đoạn B.")],
        ["Phần I"],
        client=client,
        model="m",
    )
    assert list(out) == ["c-aaa", "c-bbb"]
    assert [e.label for e in out["c-aaa"]] == ["E1"]
    assert out["c-bbb"] == []

    user_msg = captured["messages"][1]["content"]
    assert '<chunk ref="1">Đoạn A.</chunk>' in user_msg
    assert '<chunk ref="2">Đoạn B.</chunk>' in user_msg
    assert "c-aaa" not in user_msg  # chunk_id thật KHÔNG lộ vào prompt, chỉ ref
    assert captured["model"] == "m" and captured["temperature"] == 0.0


def test_refusal_lam_fail_ca_unit_thay_vi_cache_rong() -> None:
    # Cache "mọi chunk rỗng" khi bị refusal = mất event VĨNH VIỄN (resume coi là xong).
    client, _ = _stub_client(refusal="không thể trả lời")
    with pytest.raises(TimelineExtractionError, match="từ chối"):
        extract_unit_events([("c-aaa", "x")], None, client=client, model="m")


def test_khong_parse_duoc_lam_fail_ca_unit() -> None:
    client, _ = _stub_client(parsed=None)
    with pytest.raises(TimelineExtractionError, match="parse"):
        extract_unit_events([("c-aaa", "x")], None, client=client, model="m")
