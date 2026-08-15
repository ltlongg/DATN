"""Runtime config (nhóm Cấu hình hệ thống) — agent-service đọc system_config từ backend.

Khác các store index-time (chunk_store/graph_store...), bảng system_config do BACKEND sở hữu;
agent-service KHÔNG query Postgres trực tiếp mà gọi GET {backend_base_url}/internal/config
(quyết định user, xem docs/plan/system-config-plan.md §Storage roles).

Mirror ĐÚNG pattern `tools/prompts/prompt_store.get_active_prompt` ở phần cache — chỉ đổi
NGUỒN đọc từ Postgres sang HTTP, TTL/vị trí cache giữ nguyên:
- Cache in-process TTL ~60s (đồng bộ `_CACHE_TTL_SECONDS` của prompt_store): còn hạn trả thẳng
  từ RAM, hết hạn mới gọi lại HTTP.
- Backend down/lỗi/không tới được -> resolve về `RuntimeConfig()` mặc định (= y hệt giá trị
  hardcode trong Settings) VÀ vẫn cache default đó đủ TTL: answer flow KHÔNG vỡ nếu backend
  chưa lên, cũng không hammer backend khi nó đang down.

SYNC (mirror prompt_store, dùng httpx.Client) — nơi gọi (runner.py) bọc asyncio.to_thread.
"""

from __future__ import annotations

import logging
import threading
import time

import httpx
from pydantic import BaseModel, ConfigDict

from app.core.config import get_settings
from app.core.internal_auth import internal_headers

logger = logging.getLogger("agent.runtime_config")

class RuntimeConfig(BaseModel):
    """13 tham số tinh chỉnh áp dụng LIVE. Default = Y HỆT hằng trong core/config.py::Settings
    (12 retrieval) + temperature synthesize 0.0. Bỏ qua field thừa (vd `updated_at` trong
    response backend) nhờ extra='ignore'."""

    model_config = ConfigDict(extra="ignore")

    # --- retrieval ---
    rag_top_k: int = 20
    graph_top_k: int = 20
    hybrid_candidate_k: int = 30
    hybrid_rrf_k: int = 60
    rerank_top_k: int = 8
    bm25_top_k: int = 20
    graph_max_seed_entities: int = 5
    graph_max_chunks_per_seed: int = 20
    graph_hub_source_count_threshold: int = 80
    graph_max_context_items: int = 12
    graph_max_path_hops: int = 3
    graph_path_hit_weight: float = 1.5
    # --- synthesize ---
    llm_temperature: float = 0.0

_CACHE_TTL_SECONDS = 60.0
_HTTP_TIMEOUT_SECONDS = 5.0
_cache: tuple[float, RuntimeConfig] | None = None
# Single-flight: khi cache hết hạn, chỉ 1 thread gọi backend, các thread còn lại chờ rồi
# dùng lại kết quả (get_runtime_config chạy qua asyncio.to_thread -> có thể song song).
_lock = threading.Lock()

def clear_cache() -> None:
    """Xoá cache (dùng cho test)."""
    global _cache
    _cache = None

def _fetch() -> RuntimeConfig:
    """GET /internal/config từ backend. Lỗi mạng/status != 200/parse lỗi -> RuntimeConfig()
    mặc định (nuốt lỗi, để answer flow không vỡ khi backend chưa lên).

    Gửi kèm `X-Internal-Key` — endpoint này của backend đã gác auth nội bộ. Key sai/thiếu ->
    401 -> `raise_for_status` -> rơi vào nhánh fallback mặc định như backend down (đúng tinh
    thần honest fallback, nhưng log WARNING nêu tên lỗi để phân biệt khi debug).
    """
    settings = get_settings()
    url = f"{settings.backend_base_url.rstrip('/')}/internal/config"
    try:
        with httpx.Client(
            timeout=_HTTP_TIMEOUT_SECONDS, headers=internal_headers()
        ) as client:
            resp = client.get(url)
        resp.raise_for_status()
        return RuntimeConfig.model_validate(resp.json())
    except Exception as exc:  # noqa: BLE001 — lỗi đọc config KHÔNG được làm fail answer
        logger.warning("get_runtime_config dùng mặc định (backend lỗi): %s", type(exc).__name__)
        return RuntimeConfig()

def get_runtime_config() -> RuntimeConfig:
    """RuntimeConfig đang hiệu lực: từ cache nếu còn hạn, hết hạn thì gọi lại backend. Kể cả
    khi backend lỗi cũng cache giá trị mặc định đủ TTL (nhất quán prompt_store).

    Hot path (cache còn hạn) KHÔNG lấy lock. Chỉ khi hết hạn mới vào lock + double-check để
    đúng 1 thread gọi backend (single-flight), tránh stampede khi nhiều request đến cùng lúc."""
    global _cache
    if _cache is not None and _cache[0] > time.monotonic():
        return _cache[1]
    with _lock:
        # Thread khác có thể đã refresh trong lúc ta chờ lock -> kiểm lại trước khi gọi HTTP.
        if _cache is not None and _cache[0] > time.monotonic():
            return _cache[1]
        cfg = _fetch()
        _cache = (time.monotonic() + _CACHE_TTL_SECONDS, cfg)
        return cfg
