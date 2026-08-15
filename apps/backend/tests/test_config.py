"""Cấu hình hệ thống: GET/PUT /api/admin/config (require_admin) + GET /internal/config
(không JWT — xác thực bằng shared secret X-Internal-Key). Validate range + ràng buộc chéo
rerank_top_k <= hybrid_candidate_k (schema + DB CHECK). Xem docs/plan/system-config-plan.md.
"""

from __future__ import annotations

from app.core.config import get_settings
from app.core.internal_auth import INTERNAL_KEY_HEADER

_ALL_FIELDS = {
    "rag_top_k",
    "graph_top_k",
    "hybrid_candidate_k",
    "hybrid_rrf_k",
    "rerank_top_k",
    "bm25_top_k",
    "graph_max_seed_entities",
    "graph_max_chunks_per_seed",
    "graph_hub_source_count_threshold",
    "graph_max_context_items",
    "graph_max_path_hops",
    "graph_path_hit_weight",
    "llm_temperature",
    "updated_at",
}

# --- GET --------------------------------------------------------------------

def test_get_config_returns_all_fields(client, auth, db_conn) -> None:  # type: ignore[no-untyped-def]
    r = client.get("/api/admin/config", headers=auth("admin"))
    assert r.status_code == 200
    body = r.json()
    assert set(body) == _ALL_FIELDS
    assert isinstance(body["rag_top_k"], int) and body["rag_top_k"] > 0
    assert isinstance(body["graph_path_hit_weight"], (int, float))

def test_get_config_requires_admin(client, auth, db_conn) -> None:  # type: ignore[no-untyped-def]
    assert client.get("/api/admin/config", headers=auth("user")).status_code == 403

# --- PUT --------------------------------------------------------------------

def test_put_config_partial_update(client, auth, db_conn) -> None:  # type: ignore[no-untyped-def]
    admin = auth("admin")
    r = client.put("/api/admin/config", json={"rag_top_k": 15}, headers=admin)
    assert r.status_code == 200
    assert r.json()["rag_top_k"] == 15
    # đọc lại trong cùng txn phản ánh giá trị mới (chỉ đổi field đã gửi).
    assert client.get("/api/admin/config", headers=admin).json()["rag_top_k"] == 15

def test_put_config_temperature(client, auth, db_conn) -> None:  # type: ignore[no-untyped-def]
    r = client.put("/api/admin/config", json={"llm_temperature": 0.7}, headers=auth("admin"))
    assert r.status_code == 200
    assert r.json()["llm_temperature"] == 0.7

def test_put_config_rejects_nonpositive_int(client, auth, db_conn) -> None:  # type: ignore[no-untyped-def]
    r = client.put("/api/admin/config", json={"rag_top_k": 0}, headers=auth("admin"))
    assert r.status_code == 422

def test_put_config_rejects_temperature_out_of_range(client, auth, db_conn) -> None:  # type: ignore[no-untyped-def]
    r = client.put("/api/admin/config", json={"llm_temperature": 2.5}, headers=auth("admin"))
    assert r.status_code == 422

def test_put_config_rejects_rerank_gt_candidate_same_payload(client, auth, db_conn) -> None:  # type: ignore[no-untyped-def]
    # Cả hai field cùng gửi -> schema model_validator chặn (422) trước khi chạm DB.
    r = client.put(
        "/api/admin/config",
        json={"rerank_top_k": 40, "hybrid_candidate_k": 30},
        headers=auth("admin"),
    )
    assert r.status_code == 422

def test_put_config_rerank_gt_candidate_partial_hits_db_check(client, auth, db_conn) -> None:  # type: ignore[no-untyped-def]
    # Chỉ gửi rerank_top_k (hybrid_candidate_k mặc định 30) -> schema không kiểm được ->
    # DB CHECK bắt -> map về 422.
    r = client.put("/api/admin/config", json={"rerank_top_k": 999}, headers=auth("admin"))
    assert r.status_code == 422
    assert r.json()["code"] == "validation_error"

def test_put_config_rejects_explicit_null(client, auth, db_conn) -> None:  # type: ignore[no-untyped-def]
    # Gửi tường minh null cho cột NOT NULL -> chặn ở schema (422), KHÔNG rơi xuống DB thành 500.
    r = client.put("/api/admin/config", json={"rag_top_k": None}, headers=auth("admin"))
    assert r.status_code == 422

def test_put_config_requires_admin(client, auth, db_conn) -> None:  # type: ignore[no-untyped-def]
    r = client.put("/api/admin/config", json={"rag_top_k": 15}, headers=auth("user"))
    assert r.status_code == 403

# --- internal (agent-service gọi: KHÔNG JWT, xác thực bằng X-Internal-Key) ---------------

def _internal() -> dict[str, str]:
    """Header shared secret mà agent-service gửi (core/internal_auth.py)."""
    return {INTERNAL_KEY_HEADER: get_settings().internal_api_key}

def test_internal_config_accepts_internal_key(client, db_conn) -> None:  # type: ignore[no-untyped-def]
    r = client.get("/internal/config", headers=_internal())  # KHÔNG gửi Authorization
    assert r.status_code == 200
    assert set(r.json()) == _ALL_FIELDS

def test_internal_config_401_without_key(client, db_conn) -> None:  # type: ignore[no-untyped-def]
    r = client.get("/internal/config")
    assert r.status_code == 401
    assert r.json()["code"] == "unauthenticated"

def test_internal_config_401_with_wrong_key(client, db_conn) -> None:  # type: ignore[no-untyped-def]
    r = client.get("/internal/config", headers={INTERNAL_KEY_HEADER: "sai-key"})
    assert r.status_code == 401

def test_internal_config_rejects_user_jwt(client, auth, db_conn) -> None:  # type: ignore[no-untyped-def]
    """JWT admin KHÔNG mở được endpoint nội bộ — 2 loại credential khác nhau, không thay thế
    nhau (xem core/internal_auth.py)."""
    r = client.get("/internal/config", headers=auth("admin"))
    assert r.status_code == 401

def test_internal_config_reflects_admin_update(client, auth, db_conn) -> None:  # type: ignore[no-untyped-def]
    client.put("/api/admin/config", json={"graph_top_k": 7}, headers=auth("admin"))
    # agent-service đọc cùng nguồn -> thấy giá trị admin vừa đặt.
    assert client.get("/internal/config", headers=_internal()).json()["graph_top_k"] == 7
