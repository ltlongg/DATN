"""Tiền xử lý văn bản lịch sử Việt Nam trước khi chunk + index.

Sử dụng:
    from app.indexing.preprocessing import preprocess_text
    cleaned, report = preprocess_text(raw_text)
"""

from .cleaner import (
    PreprocessReport,
    preprocess_file,
    preprocess_text,
)

__all__ = ["PreprocessReport", "preprocess_file", "preprocess_text"]
