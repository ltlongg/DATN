"""Test get_runtime_config: parse response backend, fallback mặc định khi lỗi, cache TTL.

Mock httpx.Client để không gọi mạng thật (giữ agent-service test suite offline).
"""

from __future__ import annotations

import httpx
import pytest

from app.core import runtime_config as RC

# Response giả của GET /internal/config (kèm updated_at thừa — RuntimeConfig phải bỏ qua).
_PAYLOAD = {
    "rag_top_k": 11,
    "graph_top_k": 12,
    "hybrid_candidate_k": 33,
    "hybrid_rrf_k": 66,
    "rerank_top_k": 7,
    "bm25_top_k": 9,
    "graph_max_seed_entities": 4,
    "graph_max_chunks_per_seed": 15,
    "graph_hub_source_count_threshold": 90,
    "graph_max_context_items": 10,
    "graph_max_path_hops": 2,
    "graph_path_hit_weight": 2.5,
    "updated_at": "2026-07-11T00:00:00Z",
}

class _FakeResp:
    def __init__(self, status: int, payload: dict) -> None:
        self.status_code = status
        self._payload = payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "err",
                request=httpx.Request("GET", "http://x/internal/config"),
                response=httpx.Response(self.status_code),
            )

    def json(self) -> dict:
        return self._payload

def _install_client(monkeypatch, *, resp=None, exc=None, counter=None):
    """Patch runtime_config.httpx.Client -> fake trả `resp` hoặc raise `exc`; đếm số .get()."""

    class _FakeClient:
        def __init__(self, *a, **kw) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a) -> bool:
            return False

        def get(self, url: str):
            if counter is not None:
                counter["n"] += 1
            if exc is not None:
                raise exc
            return resp

    monkeypatch.setattr(RC.httpx, "Client", _FakeClient)

def test_parses_backend_response_and_ignores_extra(monkeypatch) -> None:
    _install_client(monkeypatch, resp=_FakeResp(200, _PAYLOAD))
    cfg = RC.get_runtime_config()
    assert cfg.rag_top_k == 11
    assert cfg.graph_path_hit_weight == 2.5
    assert not hasattr(cfg, "updated_at")  # field thừa bị bỏ

def test_fallback_default_on_connect_error(monkeypatch) -> None:
    _install_client(monkeypatch, exc=httpx.ConnectError("refused"))
    cfg = RC.get_runtime_config()
    assert cfg == RC.RuntimeConfig()  # đúng mặc định, không vỡ

def test_fallback_default_on_non_200(monkeypatch) -> None:
    _install_client(monkeypatch, resp=_FakeResp(500, {}))
    cfg = RC.get_runtime_config()
    assert cfg == RC.RuntimeConfig()

def test_cache_hits_within_ttl_only_one_http_call(monkeypatch) -> None:
    counter = {"n": 0}
    _install_client(monkeypatch, resp=_FakeResp(200, _PAYLOAD), counter=counter)
    a = RC.get_runtime_config()
    b = RC.get_runtime_config()
    assert counter["n"] == 1  # lần 2 lấy từ cache, không gọi HTTP lại
    assert a == b

def test_clear_cache_forces_new_http_call(monkeypatch) -> None:
    counter = {"n": 0}
    _install_client(monkeypatch, resp=_FakeResp(200, _PAYLOAD), counter=counter)
    RC.get_runtime_config()
    RC.clear_cache()
    RC.get_runtime_config()
    assert counter["n"] == 2  # sau clear_cache gọi HTTP lần nữa

def test_error_result_is_cached_for_ttl(monkeypatch) -> None:
    # Backend down -> cache default đủ TTL để không hammer backend.
    counter = {"n": 0}
    _install_client(monkeypatch, exc=httpx.ConnectError("refused"), counter=counter)
    RC.get_runtime_config()
    RC.get_runtime_config()
    assert counter["n"] == 1
