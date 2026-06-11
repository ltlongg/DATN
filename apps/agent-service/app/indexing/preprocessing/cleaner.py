"""Pipeline tiền xử lý văn bản lịch sử Việt Nam.

Thiết kế chính:
- Idempotent: chạy nhiều lần ra cùng kết quả.
- Không phá hủy nội dung: chỉ chuẩn hóa whitespace, dấu ngoặc kép, dấu gạch ngang, và sửa khoảng trắng dấu câu.
- Trả về `PreprocessReport` để caller log/quan sát những gì đã thay đổi.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path


_QUOTE_TRANSLATIONS = {
    "“": '"',  # " left double quote
    "”": '"',  # " right double quote
    "„": '"',  # „ double low-9 quote
    "‟": '"',  # ‟ double high-reversed-9 quote
    "‘": "'",  # ' left single quote
    "’": "'",  # ' right single quote
    "‚": "'",  # ‚ single low-9 quote
    "‛": "'",  # ‛ single high-reversed-9 quote
}

_DASH_TRANSLATIONS = {
    "–": "-",  # en-dash (U+2013)
    "—": "-",  # em-dash (U+2014)
    "…": "...", # ellipsis (U+2026)
}


@dataclass
class PreprocessReport:
    """Số liệu tóm tắt những thay đổi pipeline đã thực hiện."""

    original_chars: int = 0
    cleaned_chars: int = 0
    quotes_normalized: int = 0
    blank_runs_collapsed: int = 0
    soft_hyphens_removed: int = 0
    dashes_normalized: int = 0
    punctuation_spaces_fixed: int = 0
    headings_normalized: int = 0
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, int | list[str]]:
        return {
            "original_chars": self.original_chars,
            "cleaned_chars": self.cleaned_chars,
            "quotes_normalized": self.quotes_normalized,
            "blank_runs_collapsed": self.blank_runs_collapsed,
            "soft_hyphens_removed": self.soft_hyphens_removed,
            "dashes_normalized": self.dashes_normalized,
            "punctuation_spaces_fixed": self.punctuation_spaces_fixed,
            "headings_normalized": self.headings_normalized,
            "warnings": list(self.warnings),
        }


def preprocess_text(
    text: str,
    *,
    normalize_unicode: bool = True,
) -> tuple[str, PreprocessReport]:
    """Chạy toàn bộ pipeline tiền xử lý trên `text`.

    Args:
        text: Nội dung Markdown thô.
        normalize_unicode: Có chạy NFC normalization không (mặc định có).

    Returns:
        Tuple (cleaned_text, report).
    """

    report = PreprocessReport(original_chars=len(text))

    if normalize_unicode:
        text = unicodedata.normalize("NFC", text)

    # 1. Loại bỏ Soft Hyphen (U+00AD)
    text, soft_hyphens = _remove_soft_hyphens(text)
    report.soft_hyphens_removed = soft_hyphens

    # 2. Chuẩn hóa newlines
    text = _normalize_newlines(text)

    # 2b. Đảm bảo các tiêu đề được bao quanh bởi dòng trống (\n\n) để tránh bị gộp paragraph
    text = _normalize_heading_newlines(text)

    # 3. Chuẩn hóa smart quotes
    text, quotes = _normalize_quotes(text)
    report.quotes_normalized = quotes

    # 4. Chuẩn hóa dashes và ellipsis
    text, dashes = _normalize_dashes(text)
    report.dashes_normalized = dashes

    # 5. Chuẩn hóa khoảng trắng sau dấu câu (dấu chấm, phẩy dính liền chữ)
    text, punctuation_spaces = _normalize_punctuation_spacing(text)
    report.punctuation_spaces_fixed = punctuation_spaces

    # 6. Chuẩn hóa khoảng trắng trong tiêu đề Markdown
    text, headings = _normalize_heading_spacing(text)
    report.headings_normalized = headings

    # 7. Gộp blank lines thừa
    text, blank_runs = _collapse_blank_runs(text)
    report.blank_runs_collapsed = blank_runs

    text = text.strip() + "\n"
    report.cleaned_chars = len(text)
    return text, report


def preprocess_file(
    input_path: str | Path,
    output_path: str | Path | None = None,
) -> PreprocessReport:
    """Đọc file, chạy preprocess, ghi ra `output_path` (nếu có)."""

    src = Path(input_path)
    raw = src.read_text(encoding="utf-8")
    cleaned, report = preprocess_text(raw)
    if output_path is not None:
        dst = Path(output_path)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(cleaned, encoding="utf-8")
    return report


def _remove_soft_hyphens(text: str) -> tuple[str, int]:
    count = text.count("\u00ad")
    if count:
        text = text.replace("\u00ad", "")
    return text, count


def _normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _normalize_quotes(text: str) -> tuple[str, int]:
    count = sum(text.count(ch) for ch in _QUOTE_TRANSLATIONS)
    if count:
        text = text.translate({ord(k): v for k, v in _QUOTE_TRANSLATIONS.items()})
    return text, count


def _normalize_dashes(text: str) -> tuple[str, int]:
    count = sum(text.count(ch) for ch in _DASH_TRANSLATIONS)
    if count:
        text = text.translate({ord(k): v for k, v in _DASH_TRANSLATIONS.items()})
    return text, count


def _normalize_punctuation_spacing(text: str) -> tuple[str, int]:
    """Thêm khoảng trắng sau dấu chấm/dấu phẩy nếu viết liền chữ (ví dụ: tan.Sau -> tan. Sau).

    Tránh áp dụng cho chữ số (ví dụ: 19.5, 5.6.1862).
    Hỗ trợ ký tự tiếng Việt có dấu.
    """
    pattern = r"([.,])([a-zA-ZĂÂĐÊÔƠƯăâđêôơưÀ-ỹ])"
    matches = re.findall(pattern, text)
    if not matches:
        return text, 0

    text = re.sub(pattern, r"\1 \2", text)
    return text, len(matches)


def _normalize_heading_spacing(text: str) -> tuple[str, int]:
    """Chuẩn hóa khoảng trắng tiêu đề Markdown (ví dụ: ## 1.Khởi nghĩa -> ## 1. Khởi nghĩa)."""
    # Pattern: khớp đầu dòng hoặc sau ký tự xuống dòng
    # VD: '## 1.Khởi nghĩa'
    pattern = r"(^|\n)(#+)\s*(\d+\.)\s*([^\s\d#])"
    matches = re.findall(pattern, text)
    if not matches:
        return text, 0

    text = re.sub(pattern, r"\1\2 \3 \4", text)
    return text, len(matches)


def _collapse_blank_runs(text: str) -> tuple[str, int]:
    """Gộp >=3 newline liên tiếp về đúng 2 (một paragraph break)."""
    matches = re.findall(r"\n{3,}", text)
    if not matches:
        return text, 0
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text, len(matches)


def _normalize_heading_newlines(text: str) -> str:
    """Đảm bảo mọi tiêu đề (dòng bắt đầu bằng #) được bao quanh bởi đúng 1 dòng trống (tức là \n\n)."""
    lines = text.split("\n")
    new_lines = []
    n = len(lines)
    for i, line in enumerate(lines):
        stripped = line.strip()
        # Một dòng được coi là heading nếu nó bắt đầu bằng ký tự #
        if stripped.startswith("#"):
            # Thêm dòng trống phía trước nếu chưa có
            if new_lines and new_lines[-1] != "":
                new_lines.append("")
            new_lines.append(stripped)
            # Thêm dòng trống phía sau nếu dòng tiếp theo không trống
            if i + 1 < n and lines[i + 1].strip() != "":
                new_lines.append("")
        else:
            new_lines.append(line)
    return "\n".join(new_lines)


