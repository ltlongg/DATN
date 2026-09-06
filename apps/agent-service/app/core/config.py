"""Cấu hình tập trung cho agent-service.

Dùng pydantic-settings để load từ biến môi trường / file `.env`. Ở phase chunking
mới chỉ cần một tập nhỏ (LLM key, tokenizer, ngưỡng chunk); các phase sau (retrieval,
storage) sẽ bổ sung thêm field vào đây.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
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
    # Số cặp mỗi forward cross-encoder. KHÔNG phải knob hiệu năng thông thường "to hơn =
    # nhanh hơn": GPU dev còn cõng cả model embedding, nên batch to đẩy đỉnh VRAM vượt phần
    # trống -> đổ sang shared memory -> chậm gấp bội. Đo trên RTX 4060 Laptop 8.6 GB với 27
    # cặp thật: batch 30 = 25.3s, batch 8 = 2.26s. Chỉnh theo VRAM còn trống của máy chạy,
    # không chỉnh theo `hybrid_candidate_k`. Xem app/core/reranker.py.
    rerank_batch_size: int = 8
    graph_max_seed_entities: int = 5
    graph_max_chunks_per_seed: int = 20
    graph_hub_source_count_threshold: int = 80
    graph_max_context_items: int = 12
    # Path-finding giữa các seed (kích hoạt khi >=2 seed). max_path_hops = cận shortestPath
    # (nội suy vào Cypher — phải int); path_hit_weight = điểm chunk nằm trên path.
    graph_max_path_hops: int = 3
    graph_path_hit_weight: float = 1.5

    plan_llm_model: str
    resolve_llm_model: str
    synthesize_llm_model: str
    ask_max_history_messages: int = 12
    ask_max_question_chars: int = 4000
    ask_timeout_seconds: int = 60
    synthesize_max_attempts: int = 2
    stream_batch_chars: int = 160

    # --- Todo list truy hồi (agentic retrieval loop, bậc B1 + B4). Node `plan` sinh các bước;
    # mỗi bước chạy nhiều query SONG SONG, `retrieve` gộp bằng RRF theo RANK rồi cắt.
    # KHÔNG đi qua RuntimeConfig/system_config ở V1 — xem
    # docs/plan/agentic-retrieval-loop-plan.md §8 (nhét vào đó kéo theo DDL + API + UI admin).
    # `multiquery_final_k` TRÙNG GIÁ TRỊ `rerank_top_k` chứ không buộc phải bằng: mỗi query
    # đã tự cắt rerank_top_k, đây là lần cắt SAU khi gộp nhiều query trong MỘT bước.
    # `final_context_k` là lần cắt cuối, SAU khi gộp các bước (2 bước × 8 = 16 đoạn vào
    # synthesize thì gấp đôi hiện tại) — chỉ đếm answer-context, chunk provenance-only không
    # tính (§8). `retrieval_max_steps` cap CỨNG 2, le=2 để giá trị lớn hơn chết ngay lúc khởi
    # động chứ không âm thầm bị kẹp: kiến trúc tích luỹ hiện chỉ đúng ở 2 bước. ---
    multiquery_final_k: int = 8
    final_context_k: int = 10
    max_queries_per_step: int = 4
    retrieval_max_steps: int = Field(default=2, ge=1, le=2)

    # --- Guardrails input layer (v1). 1 lớp kiểm input trước `plan`, chỉ LLM structured
    # output (KHÔNG regex/keyword/blocklist). Dùng model riêng nhỏ/rẻ (KHÔNG fallback sang
    # plan/resolve/synthesize/llm_model). fail_closed=True: model lỗi/timeout -> vẫn chặn +
    # trả safe message mặc định. Xem docs/plan/guardrails-input-plan.md. ---
    guardrails_enabled: bool = True
    guardrails_llm_model: str = "gpt-4o-mini"
    guardrails_timeout_seconds: int = 8
    guardrails_fail_closed: bool = True

    # --- Backend gateway (đọc system_config qua GET /internal/config). Mirror field
    # agent_service_url phía backend, hướng ngược lại. Xem app/core/runtime_config.py. ---
    backend_base_url: str = "http://localhost:8000"

    # --- Auth nội bộ giữa 2 service (header X-Internal-Key). Dùng cho CẢ 2 chiều: gác
    # /ask + /kb/* của service này, và gửi kèm khi gọi GET /internal/config của backend.
    # Mặc định RỖNG = chưa cấu hình -> core/internal_auth.py TỪ CHỐI mọi request nội bộ
    # (fail-closed, có chủ đích: thiếu 1 dòng .env phải vỡ ồn ào chứ không mở cửa im lặng). ---
    internal_api_key: str = ""

    # --- Storage backends (đọc từ .env) ---
    neo4j_uri: str = ""
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    qdrant_host: str = ""
    qdrant_port: int = 6333
    qdrant_api_key: str = ""
    redis_url: str = ""
    database_url: str = ""
    # Connection pool Postgres (psycopg_pool): giữ sẵn connection cho hot path online
    # (hydrate chunk, timeline events, ghi llm_usage) thay vì mở/đóng mỗi lần.
    # Xem app/core/postgres.py::get_pool.
    pg_pool_min_size: int = 1
    pg_pool_max_size: int = 10

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
