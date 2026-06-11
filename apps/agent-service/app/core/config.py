"""Cấu hình tập trung cho agent-service.

Dùng pydantic-settings để load từ biến môi trường / file `.env`. Ở phase chunking
mới chỉ cần một tập nhỏ (LLM key, tokenizer, ngưỡng chunk); các phase sau (retrieval,
storage) sẽ bổ sung thêm field vào đây.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Nguồn .env DUY NHẤT của monorepo: file `.env` ở gốc repo. Trỏ tuyệt đối để chạy
# script từ thư mục nào cũng đọc đúng (trước đây env_file=".env" phụ thuộc CWD nên
# chạy từ root lại trúng file khác chạy từ apps/agent-service). Trong container,
# docker-compose nạp .env này thành biến môi trường thật (ưu tiên cao hơn file), nên
# đường dẫn không tồn tại trong container cũng vô hại.
_ROOT_ENV = Path(__file__).resolve().parents[4] / ".env"


class Settings(BaseSettings):
    """Cấu hình runtime, đọc từ môi trường (case-insensitive)."""

    model_config = SettingsConfigDict(
        env_file=str(_ROOT_ENV),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- LLM (Level 4 chunking + extract metadata nội dung) ---
    openai_api_key: str = ""
    openai_base_url: str | None = None
    llm_model: str = "gpt-4o-mini"

    # --- Tokenizer đếm token cho ngưỡng chunk ---
    # Mặc định khớp model embedding tiếng Việt; bọc qua count_tokens() để dễ swap.
    embedding_tokenizer: str = "AITeamVN/Vietnamese_Embedding"

    # --- Tham số chunking ---
    chunk_size: int = 700
    min_characters_per_chunk: int = 80

    @field_validator("openai_base_url", mode="before")
    @classmethod
    def _empty_base_url_to_none(cls, v: object) -> object:
        # .env / .env.example để OPENAI_BASE_URL= (rỗng) nghĩa là "dùng api.openai.com".
        # Chuỗi rỗng truyền vào OpenAI client sẽ gây APIConnectionError -> ép về None.
        if isinstance(v, str) and not v.strip():
            return None
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Trả về singleton Settings (cache để không parse env nhiều lần)."""
    return Settings()
