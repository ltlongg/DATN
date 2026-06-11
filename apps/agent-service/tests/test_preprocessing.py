"""Test pipeline tien xu ly."""

from __future__ import annotations

import sys
from pathlib import Path

_APP_ROOT = Path(__file__).resolve().parents[1]
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))

from app.indexing.preprocessing import preprocess_text  # noqa: E402

# Smart quote constants (tranh parse nham thanh Python string delimiter)
LDQUO = "“"  # "
RDQUO = "”"  # "
LSQUO = "‘"  # '
RSQUO = "’"  # '


def test_idempotent() -> None:
    raw = "# Tieu de\n\nNoi dung co " + LDQUO + "quote" + RDQUO + ".\n"
    once, _ = preprocess_text(raw)
    twice, _ = preprocess_text(once)
    assert once == twice


def test_quote_normalization() -> None:
    raw = "Bac Ho noi " + LDQUO + "Khong co gi quy hon doc lap tu do" + RDQUO + "."
    cleaned, report = preprocess_text(raw)
    assert LDQUO not in cleaned and RDQUO not in cleaned
    assert '"Khong co gi quy hon doc lap tu do"' in cleaned
    assert report.quotes_normalized == 2


def test_single_quote_normalization() -> None:
    raw = "Ong noi " + LSQUO + "xin chao" + RSQUO + " voi moi nguoi."
    cleaned, report = preprocess_text(raw)
    assert LSQUO not in cleaned and RSQUO not in cleaned
    assert report.quotes_normalized == 2


def test_collapse_blank_runs() -> None:
    raw = "Doan A.\n\n\n\nDoan B.\n\n\nDoan C."
    cleaned, report = preprocess_text(raw)
    assert "\n\n\n" not in cleaned
    assert report.blank_runs_collapsed == 2


def test_double_blank_line_untouched() -> None:
    raw = "Doan A.\n\nDoan B."
    cleaned, report = preprocess_text(raw)
    assert report.blank_runs_collapsed == 0
    assert "Doan A.\n\nDoan B." in cleaned


def test_report_counts_chars() -> None:
    raw = "Hello " + LDQUO + "world" + RDQUO
    cleaned, report = preprocess_text(raw)
    assert report.original_chars == len(raw)
    assert report.cleaned_chars == len(cleaned)


def test_real_dataset_excerpt() -> None:
    """Smoke test tren doan trich thuc tu lichsu.md (neu file ton tai)."""

    dataset = Path(__file__).resolve().parents[3] / "lichsu.md"
    if not dataset.exists():
        return
    raw = dataset.read_text(encoding="utf-8")[:50_000]
    cleaned, report = preprocess_text(raw)
    assert report.quotes_normalized > 0, "Dataset phai co it nhat 1 smart quote"
    assert LDQUO not in cleaned and RDQUO not in cleaned


def test_heading_isolation() -> None:
    raw = "Doan van truoc.\n## 1. Tieu de khong khoang cach\nDoan van sau."
    cleaned, _ = preprocess_text(raw)
    assert "Doan van truoc.\n\n## 1. Tieu de khong khoang cach\n\nDoan van sau." in cleaned

