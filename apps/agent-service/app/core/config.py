"""Cấu hình tập trung cho agent-service.

Dùng pydantic-settings để load từ biến môi trường / file `.env`. Ở phase chunking
mới chỉ cần một tập nhỏ (LLM key, tokenizer, ngưỡng chunk); các phase sau (retrieval,
storage) sẽ bổ sung thêm field vào đây.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Windows: huggingface_hub mặc định cache model bằng symlink -> WinError 1314 nếu user
# chưa bật Developer Mode (fastembed BM25 + sentence-transformers embedding đều tải qua
# HF Hub). Set ở đây vì config.py là entrypoint chung cho cả API lẫn script offline
# indexing -> lib đọc đúng giá trị trước khi model nào kịp cache lần đầu.
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS", "1")

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
    llm_model: str = "gpt-5.4-nano"

    # --- Tokenizer đếm token cho ngưỡng chunk ---
    # Mặc định khớp model embedding tiếng Việt; bọc qua count_tokens() để dễ swap.
    embedding_tokenizer: str = "AITeamVN/Vietnamese_Embedding"

    # --- Embedding (sinh vector thật, dùng cho vector indexing/retrieval) ---
    embedding_model: str = "AITeamVN/Vietnamese_Embedding"

    # --- Qdrant collection cho chunk vector ---
    qdrant_collection: str = "history_vn_chunks"

    # --- LLM riêng cho pass trích entity/quan hệ (None = dùng llm_model). Đặt model
    # hỗ trợ structured outputs strict nếu llm_model mặc định không hỗ trợ. ---
    graph_llm_model: str | None = None

    # --- LLM riêng cho pass trích timeline (None = dùng llm_model). Cũng cần strict
    # Structured Outputs như graph -> tách riêng để cấu hình độc lập. ---
    timeline_llm_model: str | None = None

    # --- Geocoding: Google Maps API key cho geocode địa danh -> lat/lon (Geocoding API).
    # Rỗng -> geocoder bỏ qua Google, chỉ dùng LLM fallback.
    # LƯU Ý ToS: Google chỉ cho cache lat/lon <= 30 ngày — xem docs/reference/google-maps-api.md. ---
    google_maps_api_key: str = ""

    # --- Tham số chunking ---
    chunk_size: int = 700
    min_characters_per_chunk: int = 80

    # --- Retrieval query-side (traditional / graph / hybrid). Thứ tự áp cap graph:
    # max_seed_entities -> max_chunks_per_seed -> gom+rank -> graph_top_k (cap thắng).
    # graph_max_context_items cắt graph_context độc lập với graph_top_k. ---
    rag_top_k: int = 20
    graph_top_k: int = 20
    hybrid_candidate_k: int = 30
    rerank_top_k: int = 8
    hybrid_rrf_k: int = 60
    reranker_model: str = ""  # rỗng -> skip rerank, trả theo thứ tự RRF
    # --- Sparse BM25 (fastembed client-side, fuse trong Qdrant qua Modifier.IDF) ---
    bm25_model: str = "Qdrant/bm25"      # encoder sparse của fastembed
    bm25_top_k: int = 20                  # số candidate sparse
    sparse_vector_name: str = "bm25"      # tên named sparse trong Qdrant
    # max token cho cặp (query, passage); khớp AITeamVN/Vietnamese_Reranker (256 query +
    # 2048 passage). Override qua RERANKER_MAX_LENGTH trong .env nếu cần.
    reranker_max_length: int = 2304
    graph_max_seed_entities: int = 5
    graph_max_chunks_per_seed: int = 20
    graph_hub_source_count_threshold: int = 80
    graph_max_context_items: int = 12
    # Path-finding giữa các seed (kích hoạt khi >=2 seed). max_path_hops = cận shortestPath
    # (nội suy vào Cypher — phải int); path_hit_weight = điểm chunk nằm trên path.
    graph_max_path_hops: int = 3
    graph_path_hit_weight: float = 1.5

    # --- Orchestrator / Ask API (answer flow online). orchestrator_llm_model None =
    # fallback llm_model. synthesize_max_attempts là tổng số lần synthesize (=2 -> 1 lần
    # thử + 1 retry; =1 tắt retry). stream_batch_chars: ngưỡng gom token thành batch trước
    # khi qua guardrails hook + emit (cũng cắt ở dấu kết câu). ---
    orchestrator_llm_model: str | None = None
    ask_max_history_messages: int = 12
    ask_max_question_chars: int = 4000
    ask_timeout_seconds: int = 60
    synthesize_max_attempts: int = 2
    stream_batch_chars: int = 160

    # --- Storage backends (đọc từ .env) ---
    neo4j_uri: str = ""
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    qdrant_host: str = ""
    qdrant_port: int = 6333
    qdrant_api_key: str = ""
    redis_url: str = ""
    database_url: str = ""

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
