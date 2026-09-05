"""Test build_visualization: tách marker/timeline, honest fallback, link event_id."""

from __future__ import annotations

from app.indexing.graph.normalize import normalize_name
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


def _coord(lat, lon, confidence="cao"):
    return {"lat": lat, "lon": lon, "confidence": confidence}


def _patch(monkeypatch, events, coords_by_surface):
    coords = {normalize_name(k): v for k, v in coords_by_surface.items()}
    monkeypatch.setattr(B, "select_events_by_chunks", lambda ids, db=None: events)
    monkeypatch.setattr(B, "lookup_coords", lambda norms, db=None: coords)


def test_event_co_time_va_toa_do_ra_marker_va_timeline(monkeypatch) -> None:
    _patch(monkeypatch, [_event("e1", time_start="1862", locations=["Gò Công"])], {"Gò Công": _coord(10.36, 106.67)})
    p = B.build_visualization(["c-0"])
    assert len(p.markers) == 1 and len(p.timeline) == 1
    assert p.markers[0].event_id == "e1" == p.timeline[0].event_id  # link 2 chiều
    assert p.timeline[0].located is True
    assert p.unplaced_count == 0


def test_thieu_toa_do_chi_timeline(monkeypatch) -> None:
    # Có time + location nhưng gazetteer không có toạ độ -> chỉ timeline (located=False).
    _patch(monkeypatch, [_event("e1", time_start="1862", locations=["Căn cứ Bình Cách"])], {})
    p = B.build_visualization(["c-0"])
    assert p.markers == []
    assert len(p.timeline) == 1 and p.timeline[0].located is False
    assert p.unplaced_count == 0


def test_thieu_time_chi_map(monkeypatch) -> None:
    _patch(monkeypatch, [_event("e1", time_start=None, locations=["Gò Công"])], {"Gò Công": _coord(10.36, 106.67)})
    p = B.build_visualization(["c-0"])
    assert len(p.markers) == 1 and p.timeline == []
    assert p.unplaced_count == 0


def test_thieu_ca_hai_khong_render(monkeypatch) -> None:
    _patch(monkeypatch, [_event("e1", time_start=None, locations=[])], {})
    p = B.build_visualization(["c-0"])
    assert p.markers == [] and p.timeline == []
    assert p.unplaced_count == 1


def test_nhieu_dia_diem_nhieu_marker_chung_event_id(monkeypatch) -> None:
    _patch(
        monkeypatch,
        [_event("e1", time_start="1862-12-16", locations=["Gò Công", "Bà Rịa", "Cần Giờ"])],
        {"Gò Công": _coord(10.36, 106.67), "Bà Rịa": _coord(10.5, 107.17), "Cần Giờ": _coord(10.41, 106.95)},
    )
    p = B.build_visualization(["c-0"])
    assert len(p.markers) == 3
    assert {m.event_id for m in p.markers} == {"e1"}  # cùng 1 sự kiện -> chung event_id
    assert len(p.timeline) == 1 and p.timeline[0].located is True


def test_marker_giu_confidence_cua_event(monkeypatch) -> None:
    # Tọa độ đã được duyệt thủ công nên marker dùng confidence của event.
    _patch(monkeypatch, [_event("e1", time_start="1862", locations=["X"], confidence="cao")], {"X": _coord(10.0, 106.0, "thấp")})
    p = B.build_visualization(["c-0"])
    assert p.markers[0].confidence == "cao"
    assert p.timeline[0].confidence == "cao"  # timeline giữ confidence của sự kiện


def test_rong_khi_khong_co_event(monkeypatch) -> None:
    _patch(monkeypatch, [], {})
    p = B.build_visualization(["c-0"])
    assert p.markers == [] and p.timeline == [] and p.event_count == 0


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
        {},
    )
    p = B.build_visualization(["c-0"])
    assert [t.time_start for t in p.timeline] == ["179 TCN", "XII", "1862-03"]
