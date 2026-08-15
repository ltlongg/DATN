"""Test sparse BM25 encoder (fastembed, chạy thật — model nhỏ, cache local).

Chỉ kiểm contract tích hợp: encode trả (indices, values) căn lề + dựng được Qdrant
`SparseVector`. Không kiểm giá trị BM25 cụ thể (thuộc về fastembed).
"""

from __future__ import annotations

from qdrant_client.models import SparseVector

from app.core import sparse

def test_encode_query_builds_sparse_vector() -> None:
    indices, values = sparse.encode_query("Trương Định kháng Pháp ở Gò Công")
    assert len(indices) == len(values) > 0
    sv = SparseVector(indices=indices, values=values)  # Qdrant phải chấp nhận
    assert len(sv.indices) == len(indices)

def test_encode_documents_one_per_input_and_buildable() -> None:
    out = sparse.encode_documents(["Phan Bội Châu Đông Du", "Cần Vương Hàm Nghi"])
    assert len(out) == 2
    for indices, values in out:
        assert len(indices) == len(values) > 0
        SparseVector(indices=indices, values=values)  # không raise
