"""Test segmenter: gom chunk theo heading, cap, fallback chunk-split, idempotent."""

from __future__ import annotations

from app.indexing.timeline.segmenter import build_units


def _chunk(idx: int, text: str, **headings: str) -> dict:
    return {
        "chunk_id": f"c-{idx:03d}",
        "text": text,
        "metadata": {"headings": headings, "chunk_index": idx},
    }


def _all_ids(chunks: list[dict]) -> set[str]:
    return {c["chunk_id"] for c in chunks}


def _covered(units) -> set[str]:
    out: set[str] = set()
    for u in units:
        out.update(u.source_chunk_ids)
    return out


def test_small_section_gom_tron_thanh_mot_unit() -> None:
    chunks = [
        _chunk(0, "Đoạn một.", h1="A", h2="B", h3="C"),
        _chunk(1, "Đoạn hai.", h1="A", h2="B", h3="C"),
        _chunk(2, "Đoạn ba.", h1="A", h2="B", h3="C"),
    ]
    units = build_units(chunks, cap=10_000)
    assert len(units) == 1
    u = units[0]
    assert u.source_chunk_ids == ["c-000", "c-001", "c-002"]
    assert u.heading_path == ["A", "B", "C"]  # LCP đủ cả 3 cấp vì chung hết
    assert u.unit_id == "c-000__c-002"
    assert "Đoạn một." in u.text and "Đoạn ba." in u.text


def test_lcp_dung_o_cap_chung_cuoi_cung() -> None:
    # 2 chunk khác h3 -> heading_path chỉ tới h2 (LCP).
    chunks = [
        _chunk(0, "x", h1="A", h2="B", h3="C"),
        _chunk(1, "y", h1="A", h2="B", h3="D"),
    ]
    units = build_units(chunks, cap=10_000)
    assert len(units) == 1
    assert units[0].heading_path == ["A", "B"]


def test_section_qua_cap_chia_theo_heading_con() -> None:
    # h2=B vượt cap nhưng mỗi h3 (C, D) vừa cap -> tách 2 unit theo h3, KHÔNG overlap.
    t = "x" * 40
    chunks = [
        _chunk(0, t, h1="A", h2="B", h3="C"),
        _chunk(1, t, h1="A", h2="B", h3="C"),
        _chunk(2, t, h1="A", h2="B", h3="D"),
        _chunk(3, t, h1="A", h2="B", h3="D"),
    ]
    units = build_units(chunks, cap=100)
    assert len(units) == 2
    paths = sorted(u.heading_path for u in units)
    assert paths == [["A", "B", "C"], ["A", "B", "D"]]
    assert all(u.char_len <= 100 for u in units)
    # không có chunk nào dùng lại ở 2 unit (tách theo heading, không cắt thô)
    assert _covered(units) == _all_ids(chunks)
    assert sum(len(u.source_chunk_ids) for u in units) == len(chunks)


def test_section_quai_vat_khong_heading_con_chunk_split_co_overlap() -> None:
    # Cùng path (A,B), không h3, tổng > cap -> buộc cắt theo chunk + overlap 1 chunk.
    t = "x" * 40
    chunks = [_chunk(i, t, h1="A", h2="B") for i in range(5)]
    units = build_units(chunks, cap=100)
    assert len(units) >= 2
    assert all(u.char_len <= 100 for u in units)
    assert _covered(units) == _all_ids(chunks)  # phủ đủ
    # overlap: tổng số chunk-slot > số chunk thật => có chunk dùng lại
    total_slots = sum(len(u.source_chunk_ids) for u in units)
    assert total_slots > len(chunks)
    # unit_id duy nhất
    assert len({u.unit_id for u in units}) == len(units)


def test_idempotent_va_phu_du() -> None:
    chunks = [
        _chunk(0, "y" * 30, h1="A", h2="B", h3="C"),
        _chunk(1, "y" * 30, h1="A", h2="B", h3="C"),
        _chunk(2, "y" * 30, h1="A", h2="B", h3="D"),
        _chunk(3, "y" * 30, h1="A", h2="E"),
    ]
    u1 = build_units(chunks, cap=80)
    u2 = build_units(chunks, cap=80)
    assert [u.unit_id for u in u1] == [u.unit_id for u in u2]  # tất định
    assert _covered(u1) == _all_ids(chunks)
    assert all(u.char_len <= 80 for u in u1) or any(
        len(u.source_chunk_ids) == 1 for u in u1
    )  # unit 1-chunk có thể vượt cap (1 chunk không cắt nhỏ hơn được)


def test_chunk_thieu_text_bi_bo_qua() -> None:
    chunks = [
        _chunk(0, "có nội dung", h1="A", h2="B"),
        _chunk(1, "   ", h1="A", h2="B"),  # rỗng -> bỏ
        {"chunk_id": "", "text": "x", "metadata": {}},  # thiếu id -> bỏ
    ]
    units = build_units(chunks, cap=10_000)
    assert len(units) == 1
    assert units[0].source_chunk_ids == ["c-000"]
