"""Cấu hình tập trung cho backend API gateway.

Đọc từ biến môi trường / root `.env` (nguồn config DUY NHẤT của monorepo) qua
pydantic-settings, cùng kiểu với `agent-service/app/core/config.py`. Backend chỉ là
gateway nên tập field nhỏ: auth/JWT, Postgres, và URL + timeout tới agent-service.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Nguồn .env DUY NHẤT: file `.env` ở gốc repo. apps/backend/app/core/config.py ->
# parents[4] = gốc repo. Trỏ tuyệt đối để chạy từ thư mục nào cũng đọc đúng. Trong
# container, docker-compose nạp .env thành biến môi trường thật (ưu tiên hơn file).
_ROOT_ENV = Path(__file__).resolve().parents[4] / ".env"


class Settings(BaseSettings):
    """Cấu hình runtime, đọc từ môi trường (case-insensitive)."""

    model_config = SettingsConfigDict(
        env_file=str(_ROOT_ENV),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- HTTP server ---
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    environment: str = "development"
    log_level: str = "INFO"

    # --- CORS: nhận chuỗi CSV trong .env, parse thành list. NoDecode để pydantic-settings
    # KHÔNG cố JSON-parse giá trị env (CSV không phải JSON -> SettingsError) trước khi
    # validator dưới đây tách CSV. ---
    backend_cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]

    # --- Auth / JWT ---
    backend_secret_key: str = "change-me-to-a-long-random-string"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60

    # --- Postgres (dạng SQLAlchemy URL +psycopg; psycopg.connect cần strip — xem db.py) ---
    database_url: str = ""
    # Connection pool (psycopg_pool): giữ sẵn connection để tái dùng thay vì mở/đóng mỗi
    # request (DB remote -> tiết kiệm round-trip TCP+auth). min = số conn mở sẵn lúc idle,
    # max = trần conn đồng thời. Xem db.py::get_pool.
    pg_pool_min_size: int = 1
    pg_pool_max_size: int = 10

    # --- Agent-service gateway ---
    agent_service_url: str = "http://localhost:9000"
    # Với SSE KHÔNG đặt giới hạn tổng; chỉ chặn lúc connect + idle giữa 2 token.
    agent_connect_timeout_seconds: float = 5.0
    agent_read_idle_timeout_seconds: float = 30.0

    # --- Conversation / ask: đồng bộ AskRequest của agent-service (history max_length=12,
    # question max_length=4000). Gửi vượt sẽ bị agent trả 422. ---
    ask_max_history_messages: int = 12
    ask_max_question_chars: int = 4000

    @field_validator("backend_cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, v: object) -> object:
        # .env để BACKEND_CORS_ORIGINS=a,b,c (CSV). pydantic-settings không tự tách CSV
        # cho list[str] -> tự tách ở đây. Đã là list (test/code) thì giữ nguyên.
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Trả về singleton Settings (cache để không parse env nhiều lần)."""
    return Settings()
