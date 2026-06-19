"""Chuẩn hóa tên entity để làm khóa dedup trong Neo4j.

Vấn đề: LLM trích cùng một thực thể với nhiều biến thể chữ hoa/thường + khoảng
trắng ("Quân Pháp" vs "quân Pháp" vs "Quân  Pháp") + dạng Unicode khác nhau
(NFC vs NFD — dấu tiếng Việt có thể là ký tự dựng sẵn hoặc tổ hợp). MERGE theo
`name` thô tạo node trùng. Tách `norm_name` (khóa) khỏi `name` (hiển thị) để
dedup mà không mất bản gốc đẹp cho map/timeline.

Nguyên tắc: lowercase + gộp khoảng trắng + chuẩn hóa NFC. **TUYỆT ĐỐI giữ dấu**
— bỏ dấu sẽ làm "Quảng" trùng "Quang", "Hòa" trùng "Hỏa"... sai nghĩa lịch sử.

Tầng 2a (biến đổi xác định, CHẮC CHẮN cùng một chữ, không cần duyệt):
  1. Vị trí dấu thanh trên nguyên âm đôi MỞ oa/oe/uy: "hòa"/"hoà", "khỏe"/"khoẻ",
     "thúy"/"thuý" là cùng một chữ, chỉ khác trường phái đặt dấu (kiểu cũ trên
     nguyên âm đầu, kiểu mới trên nguyên âm sau). Đưa về MỘT kiểu **kiểu cũ — dấu
     trên nguyên âm đầu** ("hòa", "thúy", "khỏe"), vì kiểu cũ vừa khớp với cụm "ua"
     (mùa/của/lụa — dấu vốn nằm đúng trên 'u') vừa nhất quán cho oa/oe/uy. Dấu thanh
     KHÔNG đổi (sắc vẫn sắc), chỉ đổi CHỖ đặt -> không phải bỏ dấu, an toàn tuyệt
     đối. Lưu ý: "Phú Yên" vs "Phù Yên" là khác DẤU THANH (sắc vs huyền) nên không
     bị đụng.

     HAI CHỐT CHẶN bắt buộc (nếu thiếu sẽ tạo chữ sai):
     - Chỉ dời khi cụm nằm CUỐI âm tiết (sau nguyên âm sau là hết/khoảng trắng).
       Âm tiết đóng hoặc tam trùng âm ("toàn", "hoàng", "quyển", "ngoài", "xoáy")
       đặt dấu trên nguyên âm chính ở CẢ HAI kiểu -> tuyệt đối không dời.
     - Bỏ qua digraph "qu": "quả", "quý" có 'u' là bán âm, dấu nằm trên nguyên âm
       sau là đúng -> lookbehind (?<!q).
  2. Gạch nối '-' coi như khoảng trắng: "Pháp-Thanh"/"Pháp - Thanh" về một khóa.
"""

from __future__ import annotations

import re
import unicodedata

__all__ = ["normalize_name"]

_WS = re.compile(r"\s+")

# Dấu thanh tổ hợp (NFD): huyền U+0300, sắc U+0301, ngã U+0303, hỏi U+0309, nặng U+0323.
_TONES = "̣̀́̃̉"
# Toàn bộ dấu tổ hợp Unicode U+0300–U+036F (dùng trong lookahead "cuối âm tiết").
_COMBINING = "̀-ͯ"
# Khớp trên chuỗi NFD biến thể KIỂU MỚI (dấu trên nguyên âm sau) để dời về KIỂU CŨ:
#   (?<!q)        không phải digraph "qu" (quả/quý: dấu trên nguyên âm sau là đúng).
#   [ou]          nguyên âm đầu o|u. Nếu mang dấu phẩm chất (ô, ư, ơ...) sẽ có
#                 horn/circumflex chen vào nên không khớp [aey] ngay sau -> tự loại.
#   [aey]         nguyên âm sau trơn (circumflex/horn đứng trước dấu thanh trong
#                 NFD nên "â/ê" không khớp được [aey] + [dấu]).
#   [_TONES]      dấu thanh đang nằm trên nguyên âm sau (dạng kiểu mới cần sửa).
#   lookahead     nguyên âm sau phải là CUỐI âm tiết: không có chữ cái hay dấu tổ
#                 hợp nào theo sau. Loại âm tiết đóng ("toàn", "hoàng") và tam
#                 trùng âm ("ngoài", "xoáy") — ở đó dấu vốn đặt đúng, không dời.
_END = rf"(?![a-zđ{_COMBINING}])"
_TONE_DIPHTHONG = re.compile(rf"(?<!q)([ou])([aey])([{_TONES}]){_END}")


def normalize_name(name: str) -> str:
    """Khóa chuẩn hóa cho tên entity.

    Lowercase + gạch nối->space + dấu thanh oa/oe/uy về kiểu cũ + trim + gộp khoảng trắng.
    Giữ nguyên dấu tiếng Việt. Idempotent: normalize_name(normalize_name(x)) == normalize_name(x).
    """
    out = name.lower()
    out = out.replace("-", " ")  # gạch nối coi như khoảng trắng
    # Dời dấu thanh cụm mở oa/oe/uy về nguyên âm ĐẦU = kiểu cũ (NFD để tách dấu tổ hợp).
    # Nhóm: \1 nguyên âm đầu, \2 nguyên âm sau, \3 dấu thanh -> \1\3\2 (dấu lên nguyên âm đầu).
    out = unicodedata.normalize("NFD", out)
    out = _TONE_DIPHTHONG.sub(r"\1\3\2", out)
    out = unicodedata.normalize("NFC", out)
    out = _WS.sub(" ", out).strip()
    return out