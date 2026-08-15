"""Gom chunk thành "unit" theo cây heading để trích atomic event.

Vì sao: trích từng chunk lẻ mất context toàn cục của sự kiện (một sự kiện trải
nhiều chunk; mốc thời gian/địa điểm nằm rải). Gom các chunk cùng nhánh heading
thành một "unit" cho LLM đọc trọn mạch sự kiện một lần, nhưng có CAP để không vượt
context window.

Unit GIỮ NGUYÊN từng chunk (`chunks: list[UnitChunk]`), KHÔNG nối thành một chuỗi
text phẳng: extractor gắn marker `ref` cho từng chunk và LLM phải trả kết quả theo
đúng từng chunk -> provenance chính xác ở CẤP CHUNK (event chỉ thuộc chunk chứa bằng
chứng, thay vì thuộc cả unit). Xem `docs/plan/timeline-extraction-by-unit-plan.md`.

Thuật toán đệ quy "shallowest-fit" (lấy đơn vị NÔNG nhất mà vẫn ≤ CAP):
  1. Một nhóm chunk cùng nhánh heading: nếu tổng ký tự ≤ CAP -> emit 1 unit
     (gom trọn cả section — context tốt nhất).
  2. Nếu > CAP -> chia theo cấp heading sâu hơn (h1->h2->h3...), đệ quy từng nhánh.
  3. Hết cấp heading mà vẫn > CAP (section "quái vật" không có heading con) -> cắt
     theo chunk: greedy nhồi tới CAP, KHÔNG overlap. Mọi part vẫn chung
     `heading_path` -> extractor luôn có "bối cảnh mục".

INVARIANT: mỗi chunk hợp lệ nằm trong ĐÚNG MỘT unit (không overlap, không bỏ sót).
Overlap cũ (lặp 1 chunk ở ranh giới) đã BỎ vì nó phá provenance cấp chunk: một chunk
thuộc 2 unit thì 2 lần gọi LLM cùng sinh event cho nó, cache theo chunk_id ghi đè
lẫn nhau. `run_segmentation.py` kiểm tra invariant này và từ chối ghi artifact nếu vỡ.

LLM-free, tất định, idempotent: cùng input -> cùng danh sách unit.
`unit_id = "{first_chunk_id}__{last_chunk_id}"` (ổn định, ascii, duy nhất, dễ đọc).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.tools.graph_rag.chunks import build_heading_path

__all__ = [
    "CAP_CHARS",
    "Unit",
    "UnitChunk",
    "build_units",
    "unit_from_dict",
    "unit_to_dict",
]

log = logging.getLogger(__name__)

# CAP 30K ký tự. Hạ từ 50K khi chuyển sang trả kết quả THEO CHUNK: một response giờ
# phải phân bổ event cho từng chunk trong unit, nên vừa phải đọc kỹ toàn unit vừa phải
# quy đúng bằng chứng về chunk — việc nặng hơn hẳn so với trả một danh sách phẳng.
# 30K (~8K token) giữ unit trong vùng LLM còn recall tốt ở MỌI vị trí context, nên bỏ
# luôn completeness pass lượt-2 của cap 50K (xem plan §8).
CAP_CHARS = 30_000

@dataclass(frozen=True)
class UnitChunk:
    """Một chunk nguyên vẹn bên trong unit (đơn vị quy kết event của LLM)."""

    chunk_id: str
    text: str

@dataclass(frozen=True)
class _Chunk:
    chunk_id: str
    text: str
    path: tuple[str, ...]  # heading_path (h1, h2, ...)

@dataclass
class Unit:
    """Một đơn vị trích: các chunk liền mạch + bối cảnh heading chung."""

    unit_id: str
    heading_path: list[str]
    chunks: list[UnitChunk]

    @property
    def chunk_ids(self) -> list[str]:
        return [c.chunk_id for c in self.chunks]

    @property
    def char_len(self) -> int:
        """Tổng ký tự nội dung — đại lượng so với CAP (không tính marker của prompt)."""
        return sum(len(c.text) for c in self.chunks)

def _prepare(chunks: list[dict]) -> list[list[_Chunk]]:
    """Lọc + gom theo TÀI LIỆU (`source_file`), mỗi khối sắp theo `chunk_index`.

    File chunks dùng CHUNG cho nhiều tài liệu, mà `chunk_index` đếm lại từ 0 ở mỗi tài
    liệu -> sort toàn cục sẽ xen kẽ các tài liệu, unit thành hổ lốn text của hai cuốn
    sách. Khối tài liệu giữ thứ tự xuất hiện trong file; trong khối sắp theo chunk_index.
    """
    blocks: dict[str, list[tuple[int, _Chunk]]] = {}
    for c in chunks:
        meta = c.get("metadata") or {}
        cid = c.get("chunk_id")
        text = c.get("text") or ""
        if not cid or not text.strip():
            continue
        path = tuple(build_heading_path(meta))
        idx = meta.get("chunk_index")
        idx = idx if isinstance(idx, int) else 0
        src = str(meta.get("source_file") or "")
        blocks.setdefault(src, []).append((idx, _Chunk(cid, text, path)))

    out: list[list[_Chunk]] = []
    for rows in blocks.values():  # dict giữ thứ tự chèn = thứ tự tài liệu trong file
        rows.sort(key=lambda r: r[0])  # stable -> hoà chunk_index thì giữ thứ tự file
        out.append([r[1] for r in rows])
    return out

def _total(items: list[_Chunk]) -> int:
    return sum(len(it.text) for it in items)

def _lcp(paths: list[tuple[str, ...]]) -> list[str]:
    """Tiền tố heading chung dài nhất (longest common prefix) của các path."""
    out: list[str] = []
    for col in zip(*paths):
        first = col[0]
        if all(c == first for c in col):
            out.append(first)
        else:
            break
    return out

def _make_unit(items: list[_Chunk]) -> Unit:
    return Unit(
        unit_id=f"{items[0].chunk_id}__{items[-1].chunk_id}",
        heading_path=_lcp([it.path for it in items]),
        chunks=[UnitChunk(it.chunk_id, it.text) for it in items],
    )

def _group(items: list[_Chunk], depth: int) -> list[list[_Chunk]]:
    """Chia thành các run LIÊN TIẾP theo heading ở cấp `depth` (giữ thứ tự).

    Chunk thiếu heading ở cấp này -> key "" (gom riêng phần "mở đầu mục" trước các
    tiểu mục có heading con). Vì chunk đã theo thứ tự văn bản nên run liên tiếp =
    đúng ranh giới section.
    """
    groups: list[list[_Chunk]] = []
    cur: list[_Chunk] = []
    cur_key: object = object()
    for it in items:
        key = it.path[depth] if depth < len(it.path) else ""
        if cur and key != cur_key:
            groups.append(cur)
            cur = []
        cur.append(it)
        cur_key = key
    if cur:
        groups.append(cur)
    return groups

def _chunk_split(items: list[_Chunk], cap: int, out: list[Unit]) -> None:
    """Section quái vật không còn heading con: cắt theo chunk, greedy tới CAP.

    KHÔNG overlap: mỗi chunk vào đúng một part. Chunk đơn lẻ dài hơn cap vẫn được giữ
    NGUYÊN VẸN thành một unit riêng (không cắt đôi nội dung) — `build_units` cảnh báo.
    """
    part: list[_Chunk] = []
    size = 0
    for it in items:
        n = len(it.text)
        if part and size + n > cap:
            out.append(_make_unit(part))
            part, size = [], 0
        part.append(it)
        size += n
    if part:
        out.append(_make_unit(part))

def _segment(items: list[_Chunk], depth: int, cap: int, out: list[Unit]) -> None:
    if not items:
        return
    if _total(items) <= cap:
        out.append(_make_unit(items))
        return
    groups = _group(items, depth)
    if len(groups) > 1:
        for g in groups:
            _segment(g, depth + 1, cap, out)
    elif any(len(it.path) > depth + 1 for it in items):
        # Cùng heading ở cấp này nhưng còn cấp sâu hơn -> thử chia sâu hơn.
        _segment(items, depth + 1, cap, out)
    else:
        _chunk_split(items, cap, out)

def build_units(chunks: list[dict], cap: int = CAP_CHARS) -> list[Unit]:
    """Gom danh sách chunk (dạng `chunks_llm.json`) thành các unit ≤ cap ký tự.

    Mỗi tài liệu (`source_file`) phân đoạn RIÊNG: một unit không bao giờ trộn text của
    hai tài liệu, kể cả khi cả hai gộp lại vẫn dưới cap.

    Chunk đơn lẻ vượt cap -> unit riêng vượt cap + CẢNH BÁO (không cắt nội dung âm thầm).
    """
    out: list[Unit] = []
    for block in _prepare(chunks):
        for it in block:
            if len(it.text) > cap:
                log.warning(
                    "Chunk %s dài %d ký tự > cap %d -> để nguyên thành unit riêng vượt cap.",
                    it.chunk_id,
                    len(it.text),
                    cap,
                )
        _segment(block, 0, cap, out)
    return out

# --- Serialize: cầu nối giữa BƯỚC 1 (run_segmentation.py ghi artifact units) và BƯỚC 2
# (run_timeline_index.py đọc lại artifact đó để trích). Giữ định dạng ở một chỗ. ---

def unit_to_dict(u: Unit) -> dict[str, object]:
    """Unit -> dict JSON (để ghi `dataset/timeline_units.json`).

    KHÔNG ghi `source_chunk_ids` riêng: suy trực tiếp từ `chunks[].chunk_id`, một
    nguồn sự thật (hai bản sao lệch nhau là bug im lặng).
    """
    return {
        "unit_id": u.unit_id,
        "heading_path": list(u.heading_path),
        "chunks": [{"chunk_id": c.chunk_id, "text": c.text} for c in u.chunks],
    }

def unit_from_dict(d: dict) -> Unit:
    """dict (đọc từ artifact units) -> Unit."""
    return Unit(
        unit_id=str(d["unit_id"]),
        heading_path=[str(x) for x in (d.get("heading_path") or [])],
        chunks=[
            UnitChunk(str(c["chunk_id"]), str(c.get("text") or ""))
            for c in (d.get("chunks") or [])
        ],
    )
