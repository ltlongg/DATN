"""Test segmenter: gom chunk theo heading, cap, cắt theo chunk KHÔNG overlap, idempotent."""

from __future__ import annotations

import logging
from collections import Counter

import pytest

from app.indexing.timeline.segmenter import Unit, build_units, unit_from_dict, unit_to_dict

def _chunk(idx: int, text: str, **headings: str) -> dict:
    return {
        "chunk_id": f"c-{idx:03d}",
        "text": text,
        "metadata": {"headings": headings, "chunk_index": idx},
    }

def _all_ids(chunks: list[dict]) -> set[str]:
    return {c["chunk_id"] for c in chunks}

def _usage(units: list[Unit]) -> Counter[str]:
    """Số unit mà mỗi chunk xuất hiện — invariant: mọi giá trị phải = 1."""
    return Counter(cid for u in units for cid in u.chunk_ids)

def test_small_section_gom_tron_thanh_mot_unit() -> None:
    chunks = [
        _chunk(0, "Đoạn một.", h1="A", h2="B", h3="C"),
        _chunk(1, "Đoạn hai.", h1="A", h2="B", h3="C"),
        _chunk(2, "Đoạn ba.", h1="A", h2="B", h3="C"),
    ]
    units = build_units(chunks, cap=10_000)
    assert len(units) == 1
    u = units[0]
    assert u.chunk_ids == ["c-000", "c-001", "c-002"]
    assert u.heading_path == ["A", "B", "C"]  # LCP đủ cả 3 cấp vì chung hết
    assert u.unit_id == "c-000__c-002"
    # Unit giữ NGUYÊN từng chunk (không nối phẳng) -> quy được event về đúng chunk.
    assert [c.text for c in u.chunks] == ["Đoạn một.", "Đoạn hai.", "Đoạn ba."]

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
    # h2=B vượt cap nhưng mỗi h3 (C, D) vừa cap -> tách 2 unit theo h3.
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
    assert set(_usage(units)) == _all_ids(chunks)
    assert all(k == 1 for k in _usage(units).values())

def test_section_quai_vat_cat_theo_chunk_KHONG_overlap() -> None:
    # Cùng path (A,B), không h3, tổng > cap -> cắt theo chunk. Mỗi chunk vào ĐÚNG 1 unit.
    t = "x" * 40
    chunks = [_chunk(i, t, h1="A", h2="B") for i in range(5)]
    units = build_units(chunks, cap=100)
    assert len(units) >= 2
    assert all(u.char_len <= 100 for u in units)
    usage = _usage(units)
    assert set(usage) == _all_ids(chunks)  # phủ đủ
    assert all(k == 1 for k in usage.values())  # KHÔNG overlap
    # tổng slot = đúng số chunk (không lặp lại chunk nào ở ranh giới)
    assert sum(len(u.chunk_ids) for u in units) == len(chunks)
    assert len({u.unit_id for u in units}) == len(units)  # unit_id duy nhất

def test_chunk_don_le_vuot_cap_thanh_unit_rieng_va_canh_bao(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Không cắt đôi nội dung chunk: giữ nguyên vẹn thành unit riêng + cảnh báo.
    chunks = [
        _chunk(0, "a" * 30, h1="A", h2="B"),
        _chunk(1, "b" * 250, h1="A", h2="B"),  # > cap
        _chunk(2, "c" * 30, h1="A", h2="B"),
    ]
    with caplog.at_level(logging.WARNING):
        units = build_units(chunks, cap=100)

    big = [u for u in units if u.chunk_ids == ["c-001"]]
    assert len(big) == 1
    assert big[0].char_len == 250  # vượt cap nhưng nguyên vẹn
    assert all(k == 1 for k in _usage(units).values())
    assert "c-001" in caplog.text and "vượt cap" in caplog.text

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
    assert [u.chunk_ids for u in u1] == [u.chunk_ids for u in u2]
    assert all(k == 1 for k in _usage(u1).values())
    assert set(_usage(u1)) == _all_ids(chunks)
    assert all(u.char_len <= 80 for u in u1)

def _doc_chunk(src: str, idx: int, text: str, **headings: str) -> dict:
    """Chunk có `source_file` — file chunks dùng chung cho nhiều tài liệu."""
    return {
        "chunk_id": f"{src}-{idx:03d}",
        "text": text,
        "metadata": {"headings": headings, "chunk_index": idx, "source_file": src},
    }

def test_khong_tron_hai_tai_lieu_vao_mot_unit() -> None:
    """Hai tài liệu nhỏ gộp lại vẫn dưới cap, nhưng KHÔNG được thành một unit."""
    chunks = [
        _doc_chunk("docA", 0, "Nội dung A một.", h1="A", h2="B"),
        _doc_chunk("docA", 1, "Nội dung A hai.", h1="A", h2="B"),
        _doc_chunk("docB", 0, "Nội dung B một.", h1="B", h2="C"),
        _doc_chunk("docB", 1, "Nội dung B hai.", h1="B", h2="C"),
    ]
    units = build_units(chunks, cap=10_000)
    assert len(units) == 2
    assert units[0].chunk_ids == ["docA-000", "docA-001"]
    assert units[1].chunk_ids == ["docB-000", "docB-001"]
    for u in units:
        assert len({cid.split("-")[0] for cid in u.chunk_ids}) == 1

def test_chunk_index_lap_lai_khong_lam_xen_ke_tai_lieu() -> None:
    """`chunk_index` đếm lại từ 0 mỗi tài liệu -> sort toàn cục sẽ xen kẽ, phải tránh."""
    chunks = [
        _doc_chunk("docA", 0, "A0 " * 20, h1="A"),
        _doc_chunk("docA", 1, "A1 " * 20, h1="A"),
        _doc_chunk("docB", 0, "B0 " * 20, h1="B"),
        _doc_chunk("docB", 1, "B1 " * 20, h1="B"),
    ]
    ids = [cid for u in build_units(chunks, cap=100) for cid in u.chunk_ids]
    assert ids == ["docA-000", "docA-001", "docB-000", "docB-001"]

def test_thu_tu_tai_lieu_theo_vi_tri_trong_file() -> None:
    """Tài liệu xuất hiện sau trong file thì unit của nó cũng đứng sau."""
    chunks = [
        _doc_chunk("docB", 0, "B trước.", h1="B"),
        _doc_chunk("docA", 0, "A sau.", h1="A"),
    ]
    units = build_units(chunks, cap=10_000)
    assert [u.chunk_ids[0] for u in units] == ["docB-000", "docA-000"]

def test_chunk_thieu_text_bi_bo_qua() -> None:
    chunks = [
        _chunk(0, "có nội dung", h1="A", h2="B"),
        _chunk(1, "   ", h1="A", h2="B"),  # rỗng -> bỏ
        {"chunk_id": "", "text": "x", "metadata": {}},  # thiếu id -> bỏ
    ]
    units = build_units(chunks, cap=10_000)
    assert len(units) == 1
    assert units[0].chunk_ids == ["c-000"]

def test_serialize_round_trip_giu_nguyen_chunk() -> None:
    """Artifact units là cầu nối bước 1 -> bước 2: encode/decode phải không mất gì."""
    chunks = [
        _chunk(0, "Đoạn một.", h1="A", h2="B"),
        _chunk(1, "Đoạn hai.", h1="A", h2="B"),
    ]
    u = build_units(chunks, cap=10_000)[0]
    d = unit_to_dict(u)
    assert d["chunks"] == [
        {"chunk_id": "c-000", "text": "Đoạn một."},
        {"chunk_id": "c-001", "text": "Đoạn hai."},
    ]
    assert "source_chunk_ids" not in d  # suy từ chunks, không lưu bản sao
    back = unit_from_dict(d)
    assert back == u
