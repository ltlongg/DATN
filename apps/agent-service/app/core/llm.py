"""Khởi tạo client LLM dùng chung.

Tách riêng để Level 4 chunking và các phase sau (extraction, answer synthesis)
tái sử dụng cùng một cấu hình. Client được cache theo (api_key, base_url, model).
"""

from __future__ import annotations

from functools import lru_cache

from openai import OpenAI

from app.core.config import get_settings


@lru_cache(maxsize=4)
def _build_client(api_key: str, base_url: str | None) -> OpenAI:
    # max_retries cao + timeout rộng: chạy nhiều luồng song song với reasoning model
    # (gpt-5 series) dễ chạm 429 TPM theo cửa sổ trượt. SDK tự backoff theo header
    # Retry-After; để 2 (mặc định) thì sustained rate limit là cạn retry -> lỗi giả.
    return OpenAI(api_key=api_key, base_url=base_url, max_retries=6, timeout=90.0)


def get_openai_client() -> OpenAI:
    """Trả về OpenAI client cấu hình từ Settings.

    Raises:
        RuntimeError: nếu chưa có OPENAI_API_KEY (gọi LLM sẽ fail).
    """
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError(
            "Chưa cấu hình OPENAI_API_KEY. Set trong .env hoặc dùng cờ --no-llm "
            "để chỉ chạy fallback chunker."
        )
    return _build_client(settings.openai_api_key, settings.openai_base_url)
