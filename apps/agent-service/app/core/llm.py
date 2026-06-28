"""Khởi tạo client LLM dùng chung.

Tách riêng để Level 4 chunking và các phase sau (extraction, answer synthesis)
tái sử dụng cùng một cấu hình. Client được cache theo (api_key, base_url).
"""

from __future__ import annotations

from functools import lru_cache

from openai import AsyncOpenAI, OpenAI

from app.core.config import get_settings


@lru_cache(maxsize=4)
def _build_client(api_key: str, base_url: str | None) -> OpenAI:
    return OpenAI(api_key=api_key, base_url=base_url, max_retries=2, timeout=60.0)


@lru_cache(maxsize=4)
def _build_async_client(api_key: str, base_url: str | None) -> AsyncOpenAI:
    return AsyncOpenAI(api_key=api_key, base_url=base_url, max_retries=2, timeout=60.0)


def get_openai_client() -> OpenAI:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError(
            "Chưa cấu hình OPENAI_API_KEY. Set trong .env hoặc dùng cờ --no-llm "
            "để chỉ chạy fallback chunker."
        )
    return _build_client(settings.openai_api_key, settings.openai_base_url)


def get_async_openai_client() -> AsyncOpenAI:
    """Async client cho orchestrator (build_query + synthesize streaming).

    Tách khỏi client sync để FastAPI/LangGraph chạy trong event loop không bị block.
    Cache theo (api_key, base_url) như client sync.
    """
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError(
            "Chưa cấu hình OPENAI_API_KEY. Set trong .env để chạy answer flow."
        )
    return _build_async_client(settings.openai_api_key, settings.openai_base_url)
