"""Đếm token theo tokenizer của model embedding.

Toàn bộ ngưỡng chunk (mặc định 700) tính theo token, KHÔNG theo ký tự. Module này
là điểm trừu tượng duy nhất: nếu sau này đổi model embedding, chỉ cần đổi
`embedding_tokenizer` trong Settings mà không phải sửa logic chunking.

Tokenizer (HuggingFace) được lazy-load và cache: lần gọi đầu tải model (~vài trăm
MB lần đầu, sau đó cache trên đĩa), các lần sau dùng lại instance trong bộ nhớ.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from app.core.config import get_settings

if TYPE_CHECKING:
    from transformers import PreTrainedTokenizerBase


@lru_cache(maxsize=2)
def _get_tokenizer(name: str) -> "PreTrainedTokenizerBase":
    # Import nội bộ để không bắt buộc cài transformers khi chỉ dùng phần khác của app.
    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained(name)


def count_tokens(text: str) -> int:
    """Trả về số token của `text` theo tokenizer cấu hình.

    Không thêm special token (chỉ đếm nội dung) để khớp với cách đo độ dài chunk.
    """
    if not text:
        return 0
    tokenizer = _get_tokenizer(get_settings().embedding_tokenizer)
    return len(tokenizer.encode(text, add_special_tokens=False))
