"""Test reconcile: event_id tất định, dedup xuyên chunk, parent_event_norm, honest.

Cache vào reconcile khoá theo **chunk_id** (một entry = một chunk), nên
`source_chunk_ids` của event lấy thẳng từ khoá ngoài cùng — provenance cấp chunk.
"""

from __future__ import annotations

from app.indexing.graph.normalize import normalize_name
from app.indexing.timeline.reconcile import reconcile_events

def _ev(
    label,
    time_start="",
    locations=None,
    parent="",
    confidence="cao",
    time_end="",
    summary="s",
    anchor=None,
    scope=None,
    source=None,
):
    """Event v8. `anchor` mặc định lấy `locations[0]` cho gọn — test nào quan tâm tới
    anchor thì truyền tường minh."""
    locations = locations or []
    return {
        "label": label,
        "summary": summary,
        "time_start": time_start,
        "time_end": time_end,
        "locations": locations,
        "location_anchor": (locations[0] if locations else "") if anchor is None else anchor,
        "location_scope": scope or ("sites" if locations else "none"),
        "location_source": source or ("text" if locations else "none"),
        "parent_event": parent,
        "confidence": confidence,
    }

def _entry(events, unit_id="u1"):
    """Một entry cache = một CHUNK (khoá ngoài cùng là chunk_id)."""
    return {"prompt_version": "timeline-extract-v8", "unit_id": unit_id, "events": events}

def test_event_co_ban_va_event_id_tat_dinh() -> None:
    cache = {
        "c-000": _entry([_ev("Ký Hiệp ước Nhâm Tuất", "1862-06-05", parent="")]),
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

def test_dedup_xuyen_chunk_gop_chunk_va_location() -> None:
    # Cùng (time, anchor, label, parent) ở 2 chunk -> gộp 1 event, hợp nhất chunk + location.
    e_a = _ev("Nghĩa quân tấn công", "1862-12-16", ["Gò Công"], parent="Khởi nghĩa Trương Định", confidence="vừa")
    e_b = _ev("Nghĩa quân tấn công", "1862-12-16", ["Gò Công", "Tân An"], parent="Khởi nghĩa Trương Định", confidence="cao")
    cache = {"c-000": _entry([e_a], "u1"), "c-001": _entry([e_b], "u2")}
    recs = reconcile_events(cache)
    assert len(recs) == 1
    rec = recs[0]
    assert set(rec["source_chunk_ids"]) == {"c-000", "c-001"}
    assert rec["locations"] == ["Gò Công", "Tân An"]  # union, giữ thứ tự xuất hiện
    assert rec["confidence"] == "cao"  # giữ bản chắc hơn

def test_cung_event_o_hai_chunk_CUNG_unit_gop_mot_event_id() -> None:
    """Rule 'nhãn nguyên văn' của prompt: cùng label+mốc+nơi ở 2 ref -> MỘT event."""
    e = _ev("Quân Pháp tấn công Đà Nẵng", "1858-09-01", ["Đà Nẵng"])
    cache = {"c-000": _entry([e], "u1"), "c-001": _entry([e], "u1")}  # cùng unit
    recs = reconcile_events(cache)
    assert len(recs) == 1
    assert recs[0]["source_chunk_ids"] == ["c-000", "c-001"]

def test_chunk_khong_cite_thi_khong_keo_theo_event_cua_chunk_khac() -> None:
    """Provenance cấp chunk: event chỉ gắn chunk làm bằng chứng, không gắn cả unit."""
    cache = {
        "c-000": _entry([_ev("Sự kiện A", "1858", ["Đà Nẵng"])], "u1"),
        "c-001": _entry([], "u1"),  # cùng unit nhưng không có event
        "c-002": _entry([_ev("Sự kiện B", "1859", ["Gia Định"])], "u1"),
    }
    recs = reconcile_events(cache)
    by_label = {r["label"]: r["source_chunk_ids"] for r in recs}
    assert by_label == {"Sự kiện A": ["c-000"], "Sự kiện B": ["c-002"]}
    assert "c-001" not in [cid for ids in by_label.values() for cid in ids]

def test_parent_khac_nhau_khong_gop() -> None:
    # Trùng time+loc+label nhưng KHÁC chiến dịch -> 2 event riêng (parent trong khoá).
    e1 = _ev("Trận đánh", "1950", ["Đông Khê"], parent="Chiến dịch Biên giới")
    e2 = _ev("Trận đánh", "1950", ["Đông Khê"], parent="Chiến dịch Cao Bằng")
    recs = reconcile_events({"c-000": _entry([e1, e2])})
    assert len(recs) == 2
    assert recs[0]["event_id"] != recs[1]["event_id"]

def test_parent_event_norm_duoc_chuan_hoa() -> None:
    recs = reconcile_events(
        {"c-000": _entry([_ev("X", "1862", parent="Khởi Nghĩa Trương Định")])}
    )
    # parent_event_norm = resolve(...)[1]; với tên không phải alias -> normalize_name
    assert recs[0]["parent_event_norm"] == normalize_name("Khởi Nghĩa Trương Định")

def test_event_khong_label_bi_bo() -> None:
    recs = reconcile_events({"c-000": _entry([_ev("  ", "1862", ["Huế"])])})
    assert recs == []

def test_honest_event_thieu_time_va_location_van_giu() -> None:
    # Thiếu cả time lẫn location vẫn là record hợp lệ (builder online lo fallback render).
    recs = reconcile_events({"c-000": _entry([_ev("Sự kiện mơ hồ", "", [])])})
    assert len(recs) == 1
    assert recs[0]["time_start"] == "" and recs[0]["locations"] == []

def test_anchor_la_khoa_dinh_danh_khong_phai_locations0() -> None:
    """v8: `locations` lệch giữa hai chunk vẫn gộp, miễn cùng anchor.

    Đây là ca v7 làm hỏng: hai chunk kể cùng một trận nhưng liệt kê địa danh theo thứ
    tự khác nhau -> `locations[0]` khác -> tách thành hai sự kiện trên timeline.
    """
    e_a = _ev("Pháp công phá các pháo đài", "1859-02-10", ["Phúc Thắng", "Lương Thiện"],
              anchor="Gia Định")
    e_b = _ev("Pháp công phá các pháo đài", "1859-02-10", ["Lương Thiện", "Danh Nghĩa"],
              anchor="Gia Định")
    recs = reconcile_events({"c-000": _entry([e_a]), "c-001": _entry([e_b])})
    assert len(recs) == 1
    assert recs[0]["location_anchor"] == "Gia Định"
    assert recs[0]["locations"] == ["Phúc Thắng", "Lương Thiện", "Danh Nghĩa"]

def test_anchor_khac_nhau_thi_khong_gop() -> None:
    """Anchor nằm trong khoá -> trùng label+time nhưng khác vùng thì là hai sự kiện."""
    e1 = _ev("Nổ súng tấn công", "1858", ["Đà Nẵng"], anchor="Đà Nẵng")
    e2 = _ev("Nổ súng tấn công", "1858", ["Đà Nẵng"], anchor="Nam Kì")
    recs = reconcile_events({"c-000": _entry([e1, e2])})
    assert len(recs) == 2
    assert recs[0]["event_id"] != recs[1]["event_id"]

def test_merge_scope_giu_ban_than_trong_area_thang_sites() -> None:
    """Lệch scope giữa hai chunk -> giữ 'area' (không chấm marker), thà bỏ sót hơn bịa nơi."""
    e_a = _ev("Phong trào lan rộng", "1861", ["Gò Công"], anchor="Nam Kì", scope="sites")
    e_b = _ev("Phong trào lan rộng", "1861", ["Gò Công"], anchor="Nam Kì", scope="area")
    recs = reconcile_events({"c-000": _entry([e_a]), "c-001": _entry([e_b])})
    assert len(recs) == 1
    assert recs[0]["location_scope"] == "area"

def test_merge_source_text_thang_context() -> None:
    """Chỉ cần MỘT chunk nêu địa điểm ngay trong câu -> địa điểm có bằng chứng trực tiếp."""
    e_a = _ev("Trận đánh", "1954", ["A1"], anchor="Điện Biên Phủ", source="context")
    e_b = _ev("Trận đánh", "1954", ["A1"], anchor="Điện Biên Phủ", source="text")
    recs = reconcile_events({"c-000": _entry([e_a]), "c-001": _entry([e_b])})
    assert len(recs) == 1
    assert recs[0]["location_source"] == "text"

def test_event_scope_area_khong_co_locations_van_giu_anchor() -> None:
    """Ca 'Đói lớn ở Trung và Bắc Kì': không nơi nào chấm được nhưng vẫn biết vùng."""
    e = _ev("Đói lớn ở Trung và Bắc Kì", "1858", [], anchor="Bắc Kì",
            scope="area", source="text")
    recs = reconcile_events({"c-000": _entry([e])})
    assert recs[0]["locations"] == []
    assert recs[0]["location_anchor"] == "Bắc Kì"
    assert recs[0]["location_scope"] == "area"

def test_sap_xep_theo_thoi_gian_rong_cuoi() -> None:
    cache = {
        "c-000": _entry(
            [
                _ev("B", "", ["X"]),  # không thời gian -> cuối
                _ev("A", "1862", ["Y"]),
                _ev("C", "1859", ["Z"]),
            ]
        )
    }
    recs = reconcile_events(cache)
    times = [r["time_start"] for r in recs]
    assert times == ["1859", "1862", ""]
