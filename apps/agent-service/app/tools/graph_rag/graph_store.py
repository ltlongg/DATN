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

from dataclasses import dataclass
from typing import Any

from neo4j import Driver, ManagedTransaction

from app.core.config import get_settings
from app.core.neo4j import get_neo4j_driver
from app.indexing.graph.alias import resolve
from app.schemas.graph import GraphExtraction
from app.schemas.retrieval import GraphContextItem, RetrievalCandidate
from app.tools.graph_rag.entity_index import EntityIndex, get_entity_index

__all__ = ["merge_graph", "match_seed_entities", "search_graph", "GraphSeed"]

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


# ===========================================================================
# Query-side: seed matching + 1-hop expand (GraphRAG retrieval)
# ===========================================================================

# Mỗi seed: lấy descriptions + source_chunk_ids của node VÀ các cạnh 1-hop để dựng
# CẢ candidate (provenance) LẪN graph_context (content). OPTIONAL MATCH cho node cô lập.
# Match VÔ HƯỚNG (recall: bắt cạnh dù seed ở đầu nào) nhưng RETURN startNode/endNode để
# giữ HƯỚNG THẬT của cạnh — seed có thể là target, không được render ngược.
_EXPAND_SEED = """
MATCH (seed:Entity {norm_name: $norm_name})
OPTIONAL MATCH (seed)-[r:REL]-(:Entity)
RETURN seed.name AS seed_name,
       seed.descriptions AS seed_descriptions,
       seed.source_chunk_ids AS seed_chunks,
       collect({keyword: r.keyword, descriptions: r.descriptions,
                source_chunk_ids: r.source_chunk_ids,
                src_name: startNode(r).name, src_norm: startNode(r).norm_name,
                tgt_name: endNode(r).name, tgt_norm: endNode(r).norm_name}) AS edges
"""

# Trọng số hạ điểm cho seed quá "hub" (degree/source_count lớn): vẫn dùng nhưng đóng góp
# ít hơn để không nhấn chìm seed đặc thù.
_HUB_WEIGHT = 0.25
_SEED_HIT = 2.0  # chunk là source của chính seed
_EDGE_HIT = 1.0  # chunk là source của một cạnh 1-hop


@dataclass(frozen=True)
class GraphSeed:
    """Một seed đã ground: mention gốc + node KG + số token (độ đặc thù)."""

    mention: str
    info: Any  # EntityInfo
    token_count: int


def match_seed_entities(
    query: str,
    *,
    seed_mentions: list[str] | None = None,
    limit: int,
    index: EntityIndex | None = None,
) -> list[GraphSeed]:
    """Sinh + ground seed (bước A) rồi sort/hub-guard/cap (bước B đối xứng indexing).

    `seed_mentions != None` -> ground trực tiếp từng mention (chiến lược 1, từ LLM).
    `seed_mentions is None`  -> token-match từ query (chiến lược 2, fallback deterministic).
    """
    index = index or get_entity_index()
    threshold = get_settings().graph_hub_source_count_threshold

    raw: list[GraphSeed] = []
    if seed_mentions is not None:
        for mention in seed_mentions:
            info = index.ground(mention)
            if info is not None:
                raw.append(
                    GraphSeed(mention=mention, info=info, token_count=len(mention.split()))
                )
    else:
        for info in index.token_match(query, limit=limit * 3):
            raw.append(
                GraphSeed(
                    mention=info.name,
                    info=info,
                    token_count=len(info.norm_name.split()),
                )
            )

    # Hub guard: bỏ seed 1-từ generic có source_count quá lớn (vd "Pháp"). Seed nhiều từ
    # đủ đặc thù nên giữ (chỉ hạ điểm lúc rank chunk).
    kept = [
        s for s in raw if not (s.token_count <= 1 and s.info.source_count > threshold)
    ]
    # Cụm nhiều token trước; ít hub (source_count thấp) trước; tie-break norm_name.
    kept.sort(key=lambda s: (-s.token_count, s.info.source_count, s.info.norm_name))

    seen: set[str] = set()
    uniq: list[GraphSeed] = []
    for s in kept:
        if s.info.norm_name in seen:
            continue
        seen.add(s.info.norm_name)
        uniq.append(s)
    return uniq[:limit]


def _join_descriptions(descriptions: Any) -> str:
    """Gộp descriptions[] (dedup, giữ thứ tự) thành một string cho LLM."""
    if not descriptions:
        return ""
    seen: set[str] = set()
    out: list[str] = []
    for desc in descriptions:
        if desc and desc not in seen:
            seen.add(desc)
            out.append(str(desc))
    return "\n".join(out)


def search_graph(
    query: str,
    *,
    seed_mentions: list[str] | None = None,
    top_k: int | None = None,
    driver: Driver | None = None,
    index: EntityIndex | None = None,
) -> tuple[list[RetrievalCandidate], list[GraphContextItem]]:
    """Trả CẢ candidate (provenance, để RRF gộp) LẪN graph_context (content cho LLM).

    Không match seed -> trả ([], []) (KHÔNG raise; orchestrator/honest answer xử lý).
    """
    settings = get_settings()
    index = index or get_entity_index()
    seeds = match_seed_entities(
        query,
        seed_mentions=seed_mentions,
        limit=settings.graph_max_seed_entities,
        index=index,
    )
    if not seeds:
        return [], []

    driver = driver or get_neo4j_driver()
    k = top_k if top_k is not None else settings.graph_top_k
    per_seed_cap = settings.graph_max_chunks_per_seed

    scores: dict[str, float] = {}
    chunk_seeds: dict[str, set[str]] = {}
    context: list[GraphContextItem] = []

    def _bump(chunk_id: str, weight: float, mention: str, counted: set[str]) -> bool:
        # cap số chunk MỖI seed (chặn bùng nổ ở hub); trả False khi đã đầy.
        if chunk_id not in counted and len(counted) >= per_seed_cap:
            return False
        counted.add(chunk_id)
        scores[chunk_id] = scores.get(chunk_id, 0.0) + weight
        chunk_seeds.setdefault(chunk_id, set()).add(mention)
        return True

    with driver.session() as session:
        for seed in seeds:
            record = session.run(_EXPAND_SEED, norm_name=seed.info.norm_name).single()
            if record is None:
                continue
            weight = (
                _HUB_WEIGHT
                if seed.info.source_count > settings.graph_hub_source_count_threshold
                else 1.0
            )
            seed_name = record["seed_name"] or seed.info.name
            counted: set[str] = set()

            context.append(
                GraphContextItem(
                    kind="entity",
                    name=seed_name,
                    norm_name=seed.info.norm_name,
                    description=_join_descriptions(record["seed_descriptions"]),
                    source_chunk_ids=list(record["seed_chunks"] or [])[:per_seed_cap],
                    matched_seed=seed.mention,
                )
            )
            for chunk_id in record["seed_chunks"] or []:
                if not _bump(chunk_id, _SEED_HIT * weight, seed.mention, counted):
                    break

            for edge in record["edges"] or []:
                if not edge or not edge.get("keyword"):
                    continue  # OPTIONAL MATCH rỗng (node cô lập) -> bỏ
                edge_chunks = list(edge.get("source_chunk_ids") or [])
                context.append(
                    GraphContextItem(
                        kind="relation",
                        # hướng THẬT của cạnh (startNode/endNode), KHÔNG ép seed = source.
                        source_name=edge.get("src_name"),
                        source_norm=edge.get("src_norm"),
                        target_name=edge.get("tgt_name"),
                        target_norm=edge.get("tgt_norm"),
                        keyword=edge.get("keyword"),
                        description=_join_descriptions(edge.get("descriptions")),
                        source_chunk_ids=edge_chunks[:per_seed_cap],
                        matched_seed=seed.mention,
                    )
                )
                for chunk_id in edge_chunks:
                    if not _bump(chunk_id, _EDGE_HIT * weight, seed.mention, counted):
                        break

    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:k]
    candidates = [
        RetrievalCandidate(
            chunk_id=chunk_id,
            source="graph",
            rank=i + 1,
            score=score,
            debug={"matched_seeds": sorted(chunk_seeds[chunk_id])},
        )
        for i, (chunk_id, score) in enumerate(ranked)
    ]

    # Dedup graph_context theo khóa cấu trúc, cap để khỏi phình prompt.
    deduped: dict[tuple[str, ...], GraphContextItem] = {}
    for item in context:
        deduped.setdefault(item.dedup_key(), item)
    graph_context = list(deduped.values())[: settings.graph_max_context_items]

    return candidates, graph_context
