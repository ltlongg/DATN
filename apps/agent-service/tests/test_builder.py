"""Test build_visualization: dựng dòng thời gian, honest fallback, giữ thứ tự của store."""

from __future__ import annotations

from app.tools.visualization import builder as B


def _event(event_id, *, label="L", time_start=None, time_end=None, locations=None, confidence="cao"):
    return {
        "event_id": event_id,
        "label": label,
        "summary": "tóm tắt",
        "time_start": time_start,
        "time_end": time_end,
        "locations": locations or [],
        "confidence": confidence,
    }


def _patch(monkeypatch, events):
    monkeypatch.setattr(B, "select_events_by_chunks", lambda ids, db=None: events)


def test_event_co_time_ra_timeline(monkeypatch) -> None:
    _patch(monkeypatch, [_event("e1", time_start="1862", locations=["Gò Công"])])
    p = B.build_visualization(["c-0"])
    assert len(p.timeline) == 1
    assert p.timeline[0].event_id == "e1"
    assert p.timeline[0].locations == ["Gò Công"]  # địa danh vẫn đi kèm, dạng CHỮ
    assert p.unplaced_count == 0


def test_thieu_time_khong_render(monkeypatch) -> None:
    # Có địa danh nhưng không có mốc thời gian -> không dựng được, đếm vào unplaced.
    _patch(monkeypatch, [_event("e1", time_start=None, locations=["Gò Công"])])
    p = B.build_visualization(["c-0"])
    assert p.timeline == []
    assert p.event_count == 1 and p.unplaced_count == 1


def test_thieu_ca_time_lan_dia_danh_khong_render(monkeypatch) -> None:
    _patch(monkeypatch, [_event("e1", time_start=None, locations=[])])
    p = B.build_visualization(["c-0"])
    assert p.timeline == []
    assert p.unplaced_count == 1


def test_nhieu_dia_diem_giu_nguyen_ca_danh_sach(monkeypatch) -> None:
    _patch(
        monkeypatch,
        [_event("e1", time_start="1862-12-16", locations=["Gò Công", "Bà Rịa", "Cần Giờ"])],
    )
    p = B.build_visualization(["c-0"])
    assert len(p.timeline) == 1
    assert p.timeline[0].locations == ["Gò Công", "Bà Rịa", "Cần Giờ"]


def test_timeline_giu_confidence_cua_event(monkeypatch) -> None:
    _patch(monkeypatch, [_event("e1", time_start="1862", locations=["X"], confidence="thấp")])
    p = B.build_visualization(["c-0"])
    assert p.timeline[0].confidence == "thấp"


def test_rong_khi_khong_co_event(monkeypatch) -> None:
    _patch(monkeypatch, [])
    p = B.build_visualization(["c-0"])
    assert p.timeline == [] and p.event_count == 0 and p.unplaced_count == 0


def test_timeline_giu_nguyen_thu_tu_cua_store(monkeypatch) -> None:
    """Thứ tự do `select_events_by_chunks` quyết (SQL ORDER BY time_sort) — builder chỉ
    giữ nguyên. Trước đây builder sort lại theo CHUỖI `time_start`, việc đó xếp sai
    '179 TCN' (cạnh năm 179 SCN) và 'XII' (rớt sau mọi chữ số) nên đã bỏ."""
    _patch(
        monkeypatch,
        [
            _event("e1", label="A", time_start="179 TCN"),
            _event("e2", label="B", time_start="XII"),
            _event("e3", label="C", time_start="1862-03"),
        ],
    )
    p = B.build_visualization(["c-0"])
    assert [t.time_start for t in p.timeline] == ["179 TCN", "XII", "1862-03"]
