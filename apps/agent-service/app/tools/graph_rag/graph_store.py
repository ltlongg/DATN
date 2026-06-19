"""Merge entity/quan hệ đã trích vào Neo4j (idempotent).

Model: label `:Entity` (key = `norm_name`, property hiển thị = `name`), relationship
type `:REL` (phân biệt bằng property `keyword`). Cypher không parametrize được
label/rel-type trong MERGE nên dùng một label + một rel-type để giữ MERGE idempotent +
truyền tham số dạng list.

Dedup theo `norm_name` (lowercase + gộp khoảng trắng + NFC, GIỮ dấu — xem
`app.indexing.graph.normalize`) để gộp các biến thể "Quân Pháp"/"quân Pháp" về một
node. `name` giữ bản gốc đẹp đầu tiên gặp, để render map/timeline. Merge xuyên chunk:
cùng `norm_name` = một node, tích lũy `source_chunk_ids` (provenance, truy ngược
Postgres) và `descriptions` (mỗi chunk một mô tả, bỏ trùng exact). `type`/`name`
first-seen thắng. Chạy entity rồi relation trong MỘT transaction để endpoint của
relation chắc chắn tồn tại; relation dùng MATCH (không MERGE) endpoint theo `norm_name`
nên relation lỡ thiếu node thì bị bỏ qua thay vì tạo node rỗng.
"""

from __future__ import annotations

from typing import Any

from neo4j import Driver, ManagedTransaction

from app.core.neo4j import get_neo4j_driver
from app.indexing.graph.alias import resolve
from app.schemas.graph import GraphExtraction

__all__ = ["merge_graph"]

_MERGE_ENTITIES = """
UNWIND $entities AS ent
MERGE (e:Entity {norm_name: ent.norm_name})
ON CREATE SET e.name = ent.name,
              e.type = ent.type,
              e.descriptions = [ent.description],
              e.source_chunk_ids = [$chunk_id]
ON MATCH SET e.name = coalesce(e.name, ent.name),
             e.type = coalesce(e.type, ent.type),
             e.descriptions = CASE WHEN ent.description IN e.descriptions
                                   THEN e.descriptions ELSE e.descriptions + ent.description END,
             e.source_chunk_ids = CASE WHEN $chunk_id IN e.source_chunk_ids
                                       THEN e.source_chunk_ids ELSE e.source_chunk_ids + $chunk_id END
"""

_MERGE_RELATIONS = """
UNWIND $relations AS rel
MATCH (s:Entity {norm_name: rel.norm_source})
MATCH (t:Entity {norm_name: rel.norm_target})
MERGE (s)-[r:REL {keyword: rel.keyword}]->(t)
ON CREATE SET r.descriptions = [rel.description],
              r.source_chunk_ids = [$chunk_id]
ON MATCH SET r.descriptions = CASE WHEN rel.description IN r.descriptions
                                   THEN r.descriptions ELSE r.descriptions + rel.description END,
             r.source_chunk_ids = CASE WHEN $chunk_id IN r.source_chunk_ids
                                       THEN r.source_chunk_ids ELSE r.source_chunk_ids + $chunk_id END
"""


def _merge_tx(
    tx: ManagedTransaction,
    chunk_id: str,
    entities: list[dict[str, Any]],
    relations: list[dict[str, Any]],
) -> None:
    if entities:
        tx.run(_MERGE_ENTITIES, entities=entities, chunk_id=chunk_id)
    if relations:
        tx.run(_MERGE_RELATIONS, relations=relations, chunk_id=chunk_id)


def merge_graph(
    chunk_id: str, extraction: GraphExtraction, driver: Driver | None = None
) -> dict[str, int]:
    """Merge entity + relation của một chunk vào Neo4j. Trả {entities, relations}.

    Tự resolve alias + tính `norm_name` (khóa dedup) từ `name`, nên hoạt động được với
    cache cũ chưa có field norm — single source of truth là `resolve` (gồm normalize +
    alias_map), không phụ thuộc input. Alias gom biến thể về canonical (tên + khóa).
    """
    entities = []
    for e in extraction.entities:
        d = e.model_dump()
        d["name"], d["norm_name"] = resolve(d["name"])
        entities.append(d)
    relations = []
    for r in extraction.relations:
        d = r.model_dump()
        _, d["norm_source"] = resolve(d["source"])
        _, d["norm_target"] = resolve(d["target"])
        relations.append(d)
    if not entities and not relations:
        return {"entities": 0, "relations": 0}

    driver = driver or get_neo4j_driver()
    with driver.session() as session:
        session.execute_write(_merge_tx, chunk_id, entities, relations)
    return {"entities": len(entities), "relations": len(relations)}
