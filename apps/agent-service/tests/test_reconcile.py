"""Test reconcile: event_id tất định, dedup xuyên unit, parent_event_norm, honest."""

from __future__ import annotations

from app.indexing.graph.normalize import normalize_name
from app.indexing.timeline.reconcile import reconcile_events


def _ev(label, time_start="", locations=None, parent="", confidence="cao", time_end="", summary="s"):
    return {
        "label": label,
        "summary": summary,
        "time_start": time_start,
        "time_end": time_end,
        "locations": locations or [],
        "parent_event": parent,
        "confidence": confidence,
    }


def _unit(chunk_ids, events):
    return {"source_chunk_ids": chunk_ids, "events": events}


def test_event_co_ban_va_event_id_tat_dinh() -> None:
    cache = {
        "u1": _unit(
            ["c-000"],
            [_ev("Ký Hiệp ước Nhâm Tuất", "1862-06-05", parent="")],
        )
    }
    r1 = reconcile_events(cache)
    r2 = reconcile_events(cache)
    assert len(r1) == 1
    rec = r1[0]
    assert rec["label"] == "Ký Hiệp ước Nhâm Tuất"
    assert rec["time_start"] == "1862-06-05"
    assert rec["source_chunk_ids"] == ["c-000"]
    # tất định: chạy lại ra đúng event_id cũ
    assert r1[0]["event_id"] == r2[0]["event_id"]
    # uuid5 -> 36 ký tự dạng chuẩn
    assert len(rec["event_id"]) == 36


def test_dedup_xuyen_unit_gop_chunk_va_location() -> None:
    # Cùng (time, loc0, label, parent) ở 2 unit -> gộp 1 event, hợp nhất chunk + location.
    e_a = _ev("Nghĩa quân tấn công", "1862-12-16", ["Gò Công"], parent="Khởi nghĩa Trương Định", confidence="vừa")
    e_b = _ev("Nghĩa quân tấn công", "1862-12-16", ["Gò Công", "Tân An"], parent="Khởi nghĩa Trương Định", confidence="cao")
    cache = {"u1": _unit(["c-000"], [e_a]), "u2": _unit(["c-001"], [e_b])}
    recs = reconcile_events(cache)
    assert len(recs) == 1
    rec = recs[0]
    assert set(rec["source_chunk_ids"]) == {"c-000", "c-001"}
    assert rec["locations"] == ["Gò Công", "Tân An"]  # union, giữ thứ tự, loc0 đầu
    assert rec["confidence"] == "cao"  # giữ bản chắc hơn


def test_parent_khac_nhau_khong_gop() -> None:
    # Trùng time+loc+label nhưng KHÁC chiến dịch -> 2 event riêng (parent trong khoá).
    e1 = _ev("Trận đánh", "1950", ["Đông Khê"], parent="Chiến dịch Biên giới")
    e2 = _ev("Trận đánh", "1950", ["Đông Khê"], parent="Chiến dịch Cao Bằng")
    recs = reconcile_events({"u1": _unit(["c-000"], [e1, e2])})
    assert len(recs) == 2
    assert recs[0]["event_id"] != recs[1]["event_id"]


def test_parent_event_norm_duoc_chuan_hoa() -> None:
    recs = reconcile_events(
        {"u1": _unit(["c-000"], [_ev("X", "1862", parent="Khởi Nghĩa Trương Định")])}
    )
    # parent_event_norm = resolve(...)[1]; với tên không phải alias -> normalize_name
    assert recs[0]["parent_event_norm"] == normalize_name("Khởi Nghĩa Trương Định")


def test_event_khong_label_bi_bo() -> None:
    recs = reconcile_events({"u1": _unit(["c-000"], [_ev("  ", "1862", ["Huế"])])})
    assert recs == []


def test_honest_event_thieu_time_va_location_van_giu() -> None:
    # Thiếu cả time lẫn location vẫn là record hợp lệ (builder online lo fallback render).
    recs = reconcile_events({"u1": _unit(["c-000"], [_ev("Sự kiện mơ hồ", "", [])])})
    assert len(recs) == 1
    assert recs[0]["time_start"] == "" and recs[0]["locations"] == []


def test_sap_xep_theo_thoi_gian_rong_cuoi() -> None:
    cache = {
        "u1": _unit(
            ["c-000"],
            [
                _ev("B", "", ["X"]),  # không thời gian -> cuối
                _ev("A", "1862", ["Y"]),
                _ev("C", "1859", ["Z"]),
            ],
        )
    }
    recs = reconcile_events(cache)
    times = [r["time_start"] for r in recs]
    assert times == ["1859", "1862", ""]
