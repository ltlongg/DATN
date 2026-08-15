"""Driver Neo4j dùng chung + bootstrap constraint/index cho knowledge graph.

Driver SYNC: pipeline indexing là CLI sync + ThreadPoolExecutor, merge chạy ở
main thread sau khi trích — không có event loop, async driver chỉ thêm phức tạp.
Retrieval phase (FastAPI async) sau này có thể thêm `get_async_neo4j_driver()` riêng;
data model độc lập driver nên không khóa lựa chọn.

Model graph: một label `:Entity` (property `norm_name` UNIQUE = khóa dedup, `name` =
hiển thị, `type`), một relationship type `:REL` (property `keyword`). Tên file trùng
tên package `neo4j` nhưng import tuyệt đối (`from neo4j import ...`) vẫn trỏ về package
đã cài, không tự tham chiếu.
"""

from __future__ import annotations

from functools import lru_cache

from neo4j import Driver, GraphDatabase

from app.core.config import get_settings

__all__ = ["get_neo4j_driver", "ensure_graph_constraints"]

_CONSTRAINTS = [
    "CREATE CONSTRAINT entity_norm_name_unique IF NOT EXISTS "
    "FOR (e:Entity) REQUIRE e.norm_name IS UNIQUE",
    "CREATE INDEX entity_type_idx IF NOT EXISTS FOR (e:Entity) ON (e.type)",
]

@lru_cache(maxsize=1)
def get_neo4j_driver() -> Driver:
    s = get_settings()
    if not (s.neo4j_uri and s.neo4j_password):
        raise RuntimeError("Thiếu NEO4J_URI/NEO4J_PASSWORD trong .env.")
    return GraphDatabase.driver(
        s.neo4j_uri,
        auth=(s.neo4j_user, s.neo4j_password),
        # Bỏ qua notification mức INFO (vd "constraint IF NOT EXISTS đã tồn tại") cho đỡ nhiễu log.
        notifications_min_severity="WARNING",
    )

def ensure_graph_constraints(driver: Driver | None = None) -> None:
    """Tạo uniqueness constraint trên (:Entity).name + index trên .type (idempotent)."""
    driver = driver or get_neo4j_driver()
    with driver.session() as session:
        for cypher in _CONSTRAINTS:
            session.run(cypher)
