"""Document reordering chống "lost in the middle" (Phần F — mục DUY NHẤT triển khai).

LLM chú ý kém ở GIỮA context dài; chunk quan trọng nên nằm ở ĐẦU và CUỐI. Nhận list đã
sắp best-first (rerank / graph score / RRF đã làm) -> xen kẽ chunk điểm cao về hai đầu,
chunk yếu dồn vào giữa. THUẦN sắp xếp: không gọi LLM, không bỏ/đổi chunk (giữ nguyên số
lượng + provenance). Áp ở bước synthesize, chung cho cả 2 mode.
"""

from __future__ import annotations

from app.schemas.retrieval import RetrievedChunk

__all__ = ["reorder_for_context"]

def reorder_for_context(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """Best-first -> best ở hai đầu, yếu ở giữa.

    Index chẵn (0,2,4..) giữ thứ tự dồn về ĐẦU; index lẻ (1,3,5..) đảo ngược dồn về CUỐI.
    Ví dụ [c0,c1,c2,c3,c4] (c0 tốt nhất) -> [c0,c2,c4,c3,c1]: c0 đầu, c1 (tốt nhì) cuối,
    c4 (yếu nhất) ở chính giữa.
    """
    head: list[RetrievedChunk] = []
    tail: list[RetrievedChunk] = []
    for i, chunk in enumerate(chunks):
        (head if i % 2 == 0 else tail).append(chunk)
    return head + tail[::-1]
