r"""Level 1 — tách tài liệu Markdown thành các `Section` theo cấu trúc heading.

Mỗi `Section` là một khối nội dung (body) nằm giữa hai dòng heading, kèm theo
chuỗi heading cha (h1..h6) tại đúng vị trí đó. Toàn bộ offset được tính tuyệt đối
trên text đầu vào (chính là `lichsu.clean.md`) để bước sau sinh citation chính xác.

Quy tắc:
- Heading ATX: dòng khớp `^#{1,6}\s+<tiêu đề>` (cấp 1..6).
- Heading in đậm đứng riêng dòng (`**...**`, `***...***`, `****...****`, ...):
  coi là cấp 7, 8, 9, ... — SỐ SAO càng nhiều thì cấp càng sâu (cấp = 5 + số
  sao). Dùng cho tiểu mục sâu hơn mức markdown ATX biểu diễn được (tối đa cấp
  6); xem `_BOLD_HEADING_RE`. Số sao mở/đóng phải khớp nhau (vd `**A**` hợp lệ,
  `**A***` thì không).
- Khi gặp heading cấp N (dù ATX hay in đậm — CÙNG một cơ chế, vì cấp chỉ là số
  nguyên): chốt body đang tích lũy (gắn với heading stack hiện tại), rồi xóa
  mọi heading cấp >= N trong stack và đặt heading mới. Nhờ vậy heading in đậm
  cấp sâu vẫn lồng/thay-anh-em đúng như heading ATX, không cần logic riêng.
- Body rỗng / chỉ whitespace bị bỏ qua (ví dụ hai heading liền nhau).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Regex nhận diện heading markdown:
#   ^         : bắt đầu dòng
#   (#{1,6})  : khớp 1 đến 6 ký tự # đầu dòng, tức heading cấp 1..6
#   \s+       : có ít nhất 1 khoảng trắng sau dấu #
#   (.*\S)    : lấy phần tiêu đề; .* là bất kỳ ký tự gì, \S đảm bảo tiêu đề không rỗng
#   \s*$      : cho phép khoảng trắng ở cuối dòng rồi kết thúc dòng
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")

# Markdown ATX chỉ tới cấp 6 (######). Một số tài liệu (vd corpus lịch sử) có
# tiểu mục sâu hơn cấp 6 nên nguồn đánh dấu bằng "tiêu đề in đậm đứng riêng một
# dòng", số sao tăng dần theo độ sâu (`**Tiêu đề**` = cấp 7, `***Tiêu đề***` =
# cấp 8, `****Tiêu đề****` = cấp 9, ...). Ta coi ĐÓ là heading thật để chunker
# không cắt ngang tiêu đề khỏi thân, và để nó vào heading_path đúng tầng.
#   (\*{2,})  : nhóm 1 — 2 dấu * trở lên, ghi nhớ để đòi khớp lại ở cuối dòng
#   \s*       : cho phép khoảng trắng sát trong cặp sao
#   (.+?)     : tiêu đề (ít nhất 1 ký tự, non-greedy)
#   \1        : bắt buộc ĐÚNG số sao đã mở (không nhận "**A***" lệch cặp)
#   [:：]?    : cho phép 1 dấu hai chấm cuối (di chứng OCR), sẽ bị strip
# Lưu ý: dòng toàn dấu * (vd `***` thematic break) KHÔNG khớp vì thiếu (.+?).
_BOLD_HEADING_RE = re.compile(r"^\s*(\*{2,})\s*(.+?)\s*\1\s*[:：]?\s*$")
# Cấp = 5 + số sao: ** -> 7, *** -> 8, **** -> 9, ... (nối tiếp ngay sau ATX 1-6).
_BOLD_HEADING_LEVEL_OFFSET = 5

@dataclass
class Section:
    """Một khối body cùng chuỗi heading cha của nó.

    Attributes:
        headings: dict thứ tự {"h1": ..., "h2": ...} theo cấp đang hiệu lực.
        body: nội dung thô của section (slice nguyên văn từ text gốc).
        abs_start: offset ký tự bắt đầu body trong text gốc.
        abs_end: offset ký tự kết thúc body (exclusive) trong text gốc.
    """

    headings: dict[str, str]
    body: str
    abs_start: int
    abs_end: int

def _match_heading(line: str) -> tuple[int, str] | None:
    m = _HEADING_RE.match(line)
    if m:
        return len(m.group(1)), m.group(2).strip()
    b = _BOLD_HEADING_RE.match(line)
    if b:
        level = _BOLD_HEADING_LEVEL_OFFSET + len(b.group(1))
        return level, b.group(2).strip().rstrip(":：").strip()
    return None

def _stack_to_headings(stack: dict[int, str]) -> dict[str, str]:
    return {f"h{level}": stack[level] for level in sorted(stack)}

def parse_sections(text: str) -> list[Section]:
    """Tách `text` thành danh sách Section (Level 1 của pipeline chunking)."""

    sections: list[Section] = []
    stack: dict[int, str] = {}
    body_start = 0
    pos = 0

    def flush(body_end: int) -> None:
        body = text[body_start:body_end]
        if body.strip():
            sections.append(
                Section(
                    headings=_stack_to_headings(stack),
                    body=body,
                    abs_start=body_start,
                    abs_end=body_end,
                )
            )

    for line in text.splitlines(keepends=True):
        heading = _match_heading(line)
        if heading is not None:
            # Chốt body trước dòng heading này.
            flush(pos)
            level, title = heading
            for existing in [lv for lv in stack if lv >= level]:
                del stack[existing]
            stack[level] = title
            # Body kế tiếp bắt đầu ngay sau dòng heading.
            body_start = pos + len(line)
        pos += len(line)

    # Chốt body cuối tài liệu.
    flush(len(text))
    return sections
