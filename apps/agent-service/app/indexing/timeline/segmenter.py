"""Gom chunk thành "unit" theo cây heading để trích atomic event.

Vì sao: trích từng chunk lẻ mất context toàn cục của sự kiện (một sự kiện trải
nhiều chunk; mốc thời gian/địa điểm nằm rải). Gom các chunk cùng nhánh heading
thành một "unit" cho LLM đọc trọn mạch sự kiện một lần, nhưng có CAP để không vượt
context window.

Thuật toán đệ quy "shallowest-fit" (lấy đơn vị NÔNG nhất mà vẫn ≤ CAP):
  1. Một nhóm chunk cùng nhánh heading: nếu tổng ký tự ≤ CAP -> emit 1 unit
     (gom trọn cả section — context tốt nhất).
  2. Nếu > CAP -> chia theo cấp heading sâu hơn (h1->h2->h3...), đệ quy từng nhánh.
  3. Hết cấp heading mà vẫn > CAP (section "quái vật" không có heading con) -> cắt
     theo chunk: greedy nhồi tới CAP, + overlap nhẹ 1 chunk để sự kiện ở ranh giới
     không bị mất. Mọi part vẫn chung `heading_path` -> extractor luôn có "bối cảnh
     mục".

LLM-free, tất định, idempotent: cùng input -> cùng danh sách unit.
`unit_id = "{first_chunk_id}__{last_chunk_id}"` (ổn định, ascii, duy nhất, dễ đọc).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.tools.graph_rag.chunks import build_heading_path

__all__ = ["Unit", "build_units", "CAP_CHARS", "unit_to_dict", "unit_from_dict"]

# CAP 50K ký tự: điểm "ngon nhất" đo thật trên corpus — cap lớn nhất mà (1) không
# unit nào vượt ~15K token (vùng recall LLM yếu), (2) không phải cắt cứng theo chunk
# (mọi unit vẫn là một mục liền mạch theo heading), (3) phần thân gần như không đổi.
# Hạ thấp hơn (40K) bắt đầu cắt cứng vô ích; cao hơn (60K+) lọt unit quá khổ.
# Đo: 186 unit, median ~7.3K chữ, max ~49.7K chữ, overlap=0. Unit lớn (> ~40K chữ)
# được completeness pass ở extractor làm lưới chống sót.
CAP_CHARS = 50_000
_SEP = "\n\n"
_SEP_LEN = len(_SEP)
_OVERLAP = 1  # số chunk overlap khi buộc phải cắt theo chunk


@dataclass(frozen=True)
class _Chunk:
    chunk_id: str
    text: str
    path: tuple[str, ...]  # heading_path (h1, h2, ...)


@dataclass
class Unit:
    """Một đơn vị trích: text đã gom + bối cảnh heading + provenance chunk."""

    unit_id: str
    heading_path: list[str]
    text: str
    source_chunk_ids: list[str]

    @property
    def char_len(self) -> int:
        return len(self.text)


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
    if not items:
        return 0
    return sum(len(it.text) for it in items) + _SEP_LEN * (len(items) - 1)


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
    text = _SEP.join(it.text for it in items)
    ids = [it.chunk_id for it in items]
    path = _lcp([it.path for it in items]) if items else []
    return Unit(
        unit_id=f"{ids[0]}__{ids[-1]}",
        heading_path=path,
        text=text,
        source_chunk_ids=ids,
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
    """Section quái vật không còn heading con: cắt theo chunk, greedy tới CAP, +overlap."""
    n = len(items)
    i = 0
    while i < n:
        part: list[_Chunk] = []
        size = 0
        j = i
        while j < n:
            add = len(items[j].text) + (_SEP_LEN if part else 0)
            if part and size + add > cap:
                break
            part.append(items[j])
            size += add
            j += 1
        out.append(_make_unit(part))
        if j >= n:
            break
        i = max(j - _OVERLAP, i + 1)  # lùi lại overlap chunk; luôn tiến để không kẹt


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
    """
    out: list[Unit] = []
    for block in _prepare(chunks):
        _segment(block, 0, cap, out)
    return out


# --- Serialize: cầu nối giữa BƯỚC 1 (run_segmentation.py ghi artifact units) và BƯỚC 2
# (run_timeline_index.py đọc lại artifact đó để trích). Giữ định dạng ở một chỗ. ---


def unit_to_dict(u: Unit) -> dict[str, object]:
    """Unit -> dict JSON (để ghi `dataset/timeline_units.json`)."""
    return {
        "unit_id": u.unit_id,
        "heading_path": list(u.heading_path),
        "source_chunk_ids": list(u.source_chunk_ids),
        "text": u.text,
    }


def unit_from_dict(d: dict) -> Unit:
    """dict (đọc từ artifact units) -> Unit."""
    return Unit(
        unit_id=str(d["unit_id"]),
        heading_path=[str(x) for x in (d.get("heading_path") or [])],
        text=str(d.get("text") or ""),
        source_chunk_ids=[str(x) for x in (d.get("source_chunk_ids") or [])],
    )
