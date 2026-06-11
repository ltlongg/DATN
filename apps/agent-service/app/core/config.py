"""Cấu hình tập trung cho agent-service.

Dùng pydantic-settings để load từ biến môi trường / file `.env`. Ở phase chunking
mới chỉ cần một tập nhỏ (LLM key, tokenizer, ngưỡng chunk); các phase sau (retrieval,
storage) sẽ bổ sung thêm field vào đây.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Cấu hình runtime, đọc từ môi trường (case-insensitive)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- LLM (dùng cho Level 4 chunking) ---
    openai_api_key: str = ""
    openai_base_url: str | None = None
    llm_model: str = "gpt-5.4-mini"

    # --- Tokenizer đếm token cho ngưỡng chunk ---
    # Mặc định khớp model embedding tiếng Việt; bọc qua count_tokens() để dễ swap.
    embedding_tokenizer: str = "AITeamVN/Vietnamese_Embedding"

    # --- Tham số chunking ---
    chunk_size: int = 700
    min_characters_per_chunk: int = 80


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Trả về singleton Settings (cache để không parse env nhiều lần)."""
    return Settings()
