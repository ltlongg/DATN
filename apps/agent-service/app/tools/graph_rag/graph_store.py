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

import itertools
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from neo4j import Driver, ManagedTransaction

from app.core.config import get_settings
from app.core.neo4j import get_neo4j_driver
from app.indexing.graph.alias import resolve
from app.schemas.graph import GraphExtraction
from app.schemas.retrieval import GraphContextItem, RetrievalCandidate
from app.tools.graph_rag.entity_index import EntityIndex, get_entity_index

__all__ = [
    "merge_graph",
    "match_seed_entities",
    "search_graph",
    "GraphSeed",
    "list_entities",
    "count_entities",
    "get_entity",
]

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


# shortestPath giữa 2 seed (C2): trả node + relation TRÊN đường nối để trả lời câu hỏi
# quan hệ. Match VÔ HƯỚNG (recall) nhưng RETURN startNode/endNode giữ hướng thật của cạnh.
def _path_cypher(max_hop: int) -> str:
    """Sinh Cypher shortestPath với cận var-length = `max_hop`.

    Neo4j KHÔNG parametrize được cận var-length nên phải nội suy literal vào chuỗi (cùng lý
    do file này không parametrize label/rel-type). `max_hop` là hằng config, KHÔNG phải input
    user; assert int để chặn injection nếu ai đó lỡ truyền chuỗi.
    """
    assert isinstance(max_hop, int) and max_hop >= 1, "max_hop phải là int >= 1"
    return f"""
MATCH path = shortestPath(
  (a:Entity {{norm_name: $a}})-[:REL*1..{max_hop}]-(b:Entity {{norm_name: $b}})
)
RETURN [n IN nodes(path) | {{name: n.name, norm: n.norm_name,
                            descriptions: n.descriptions, chunks: n.source_chunk_ids}}] AS nodes,
       [r IN relationships(path) | {{keyword: r.keyword, descriptions: r.descriptions,
                                     chunks: r.source_chunk_ids,
                                     src_name: startNode(r).name, src_norm: startNode(r).norm_name,
                                     tgt_name: endNode(r).name, tgt_norm: endNode(r).norm_name}}] AS rels
"""


@dataclass(frozen=True)
class GraphSeed:
    """Một seed đã ground: mention gốc + node KG + số token (độ đặc thù)."""

    mention: str
    info: Any  # EntityInfo
    token_count: int


def match_seed_entities(
    seed_mentions: Sequence[str],
    *,
    limit: int,
    hub_source_count_threshold: int | None = None,
    index: EntityIndex | None = None,
) -> list[GraphSeed]:
    """Ground từng mention -> node KG, rồi sort/hub-guard/cap (đối xứng bước indexing).

    `seed_mentions` là NGUỒN SEED DUY NHẤT: mention do node `plan` trích và đã qua guard ở
    `orchestrator/planning.py`. Rỗng -> không seed -> graph tắt cho query đó; KHÔNG còn
    fallback dò tên từ chuỗi câu hỏi (xem `entity_index`).

    `hub_source_count_threshold` None -> fallback settings (Cấu hình hệ thống truyền vào).
    """
    index = index or get_entity_index()
    threshold = (
        hub_source_count_threshold
        if hub_source_count_threshold is not None
        else get_settings().graph_hub_source_count_threshold
    )

    raw: list[GraphSeed] = []
    for mention in seed_mentions:
        info = index.ground(mention)
        if info is not None:
            raw.append(
                GraphSeed(mention=mention, info=info, token_count=len(mention.split()))
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
    seed_mentions: Sequence[str],
    *,
    top_k: int | None = None,
    max_seed_entities: int | None = None,
    max_chunks_per_seed: int | None = None,
    hub_source_count_threshold: int | None = None,
    max_context_items: int | None = None,
    max_path_hops: int | None = None,
    path_hit_weight: float | None = None,
    driver: Driver | None = None,
    index: EntityIndex | None = None,
) -> tuple[list[RetrievalCandidate], list[GraphContextItem]]:
    """Trả CẢ candidate (provenance, để RRF gộp) LẪN graph_context (content cho LLM).

    Nhận thẳng danh sách mention chứ KHÔNG nhận câu hỏi: từ khi bỏ token-match, graph không
    còn đọc chuỗi query dưới bất kỳ hình thức nào — nó chỉ đi từ seed. Seed rỗng hoặc không
    ground được -> trả ([], []) (KHÔNG raise; orchestrator/honest answer xử lý).

    Các kwarg tinh chỉnh None -> fallback settings (Cấu hình hệ thống truyền giá trị admin).
    """
    settings = get_settings()
    index = index or get_entity_index()
    hub_threshold = (
        hub_source_count_threshold
        if hub_source_count_threshold is not None
        else settings.graph_hub_source_count_threshold
    )
    seeds = match_seed_entities(
        seed_mentions,
        limit=max_seed_entities if max_seed_entities is not None else settings.graph_max_seed_entities,
        hub_source_count_threshold=hub_threshold,
        index=index,
    )
    if not seeds:
        return [], []

    driver = driver or get_neo4j_driver()
    k = top_k if top_k is not None else settings.graph_top_k
    per_seed_cap = (
        max_chunks_per_seed if max_chunks_per_seed is not None else settings.graph_max_chunks_per_seed
    )

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
                if seed.info.source_count > hub_threshold
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

        # --- C2: path-finding giữa từng cặp seed (chỉ khi >=2 seed) ---
        # Số cặp = C(n,2), cap seed=5 -> tối đa 10 cặp; shortestPath = 1 đường/cặp -> không bùng nổ.
        if len(seeds) >= 2:
            path_cypher = _path_cypher(
                max_path_hops if max_path_hops is not None else settings.graph_max_path_hops
            )
            path_weight = (
                path_hit_weight if path_hit_weight is not None else settings.graph_path_hit_weight
            )
            path_counted: set[str] = set()  # cap TỔNG chunk path (chung mọi cặp)
            for a, b in itertools.combinations(seeds, 2):
                rec = session.run(
                    path_cypher, a=a.info.norm_name, b=b.info.norm_name
                ).single()
                if rec is None:
                    continue  # không có đường nối -> bỏ qua cặp (honest, không bịa)
                pair_tag = f"{a.mention}↔{b.mention}"
                for node in rec["nodes"] or []:
                    if not node or not node.get("norm"):
                        continue
                    context.append(
                        GraphContextItem(
                            kind="entity",
                            name=node.get("name"),
                            norm_name=node.get("norm"),
                            description=_join_descriptions(node.get("descriptions")),
                            source_chunk_ids=list(node.get("chunks") or [])[:per_seed_cap],
                            matched_seed=pair_tag,
                        )
                    )
                    for chunk_id in node.get("chunks") or []:
                        if not _bump(chunk_id, path_weight, pair_tag, path_counted):
                            break
                for rel in rec["rels"] or []:
                    if not rel or not rel.get("keyword"):
                        continue
                    rel_chunks = list(rel.get("chunks") or [])
                    context.append(
                        GraphContextItem(
                            kind="relation",
                            source_name=rel.get("src_name"),
                            source_norm=rel.get("src_norm"),
                            target_name=rel.get("tgt_name"),
                            target_norm=rel.get("tgt_norm"),
                            keyword=rel.get("keyword"),
                            description=_join_descriptions(rel.get("descriptions")),
                            source_chunk_ids=rel_chunks[:per_seed_cap],
                            matched_seed=pair_tag,
                        )
                    )
                    for chunk_id in rel_chunks:
                        if not _bump(chunk_id, path_weight, pair_tag, path_counted):
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
    max_ctx = max_context_items if max_context_items is not None else settings.graph_max_context_items
    graph_context = list(deduped.values())[:max_ctx]

    return candidates, graph_context


# ===========================================================================
# Read-side cho KB Inspector (admin, read-only) — xem backend-additions-plan.md §2.2
# ===========================================================================

# Lọc theo type/q/chunk_id độc lập (mỗi filter None = bỏ qua). $chunk_id lọc entity tham
# chiếu một chunk (source_chunk_ids đã có sẵn trên node, xem _MERGE_ENTITIES).
_LIST_ENTITIES = """
MATCH (e:Entity)
WHERE ($type IS NULL OR e.type = $type)
  AND ($q IS NULL OR toLower(e.name) CONTAINS toLower($q))
  AND ($chunk_id IS NULL OR $chunk_id IN e.source_chunk_ids)
RETURN e.name AS name, e.norm_name AS norm_name, e.type AS type,
       size(e.descriptions) AS description_count,
       size(e.source_chunk_ids) AS source_chunk_count
ORDER BY e.norm_name
SKIP $offset LIMIT $limit
"""

_COUNT_ENTITIES = """
MATCH (e:Entity)
WHERE ($type IS NULL OR e.type = $type)
  AND ($q IS NULL OR toLower(e.name) CONTAINS toLower($q))
  AND ($chunk_id IS NULL OR $chunk_id IN e.source_chunk_ids)
RETURN count(e) AS total
"""

# Ego-graph: node trung tâm + cạnh 1-hop (vô hướng để bắt cả cạnh vào/ra) kèm neighbor.
# startNode/endNode giữ HƯỚNG THẬT của cạnh; nb là node còn lại (để dựng danh sách neighbor).
_GET_ENTITY = """
MATCH (e:Entity {norm_name: $norm_name})
OPTIONAL MATCH (e)-[r:REL]-(nb:Entity)
RETURN e.name AS name, e.norm_name AS norm_name, e.type AS type,
       e.descriptions AS descriptions, e.source_chunk_ids AS source_chunk_ids,
       collect(CASE WHEN r IS NULL THEN NULL ELSE {
           keyword: r.keyword, descriptions: r.descriptions,
           source_chunk_ids: r.source_chunk_ids,
           src_name: startNode(r).name, src_norm: startNode(r).norm_name,
           tgt_name: endNode(r).name, tgt_norm: endNode(r).norm_name,
           nb_name: nb.name, nb_norm: nb.norm_name, nb_type: nb.type
       } END) AS edges
"""


def _clean(value: str | None) -> str | None:
    """None/rỗng -> None (bỏ filter); ngược lại strip."""
    if value is None:
        return None
    v = value.strip()
    return v or None


def count_entities(
    *,
    type: str | None = None,
    q: str | None = None,
    chunk_id: str | None = None,
    driver: Driver | None = None,
) -> int:
    driver = driver or get_neo4j_driver()
    with driver.session() as session:
        record = session.run(
            _COUNT_ENTITIES, type=_clean(type), q=_clean(q), chunk_id=_clean(chunk_id)
        ).single()
    return int(record["total"]) if record else 0


def list_entities(
    *,
    type: str | None = None,
    q: str | None = None,
    chunk_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
    driver: Driver | None = None,
) -> list[dict[str, Any]]:
    """List `:Entity` (paginate). Lọc theo type/q(name)/chunk_id độc lập; sort norm_name."""
    driver = driver or get_neo4j_driver()
    with driver.session() as session:
        result = session.run(
            _LIST_ENTITIES,
            type=_clean(type),
            q=_clean(q),
            chunk_id=_clean(chunk_id),
            limit=limit,
            offset=offset,
        )
        return [
            {
                "name": r["name"],
                "norm_name": r["norm_name"],
                "type": r["type"],
                "description_count": int(r["description_count"]),
                "source_chunk_count": int(r["source_chunk_count"]),
            }
            for r in result
        ]


def get_entity(
    norm_name: str, *, driver: Driver | None = None
) -> dict[str, Any] | None:
    """Ego-graph 1-hop của entity theo `norm_name`: node + edges có cấu trúc + neighbor.

    Trả None nếu không có node. Neighbor suy từ edges (distinct theo norm), giữ hướng thật.
    """
    driver = driver or get_neo4j_driver()
    with driver.session() as session:
        record = session.run(_GET_ENTITY, norm_name=norm_name).single()
    if record is None:
        return None

    edges: list[dict[str, Any]] = []
    neighbors: dict[str, dict[str, Any]] = {}
    for edge in record["edges"] or []:
        if not edge or not edge.get("keyword"):
            continue  # OPTIONAL MATCH rỗng (node cô lập) -> bỏ
        edges.append(
            {
                "source_name": edge.get("src_name"),
                "source_norm": edge.get("src_norm"),
                "target_name": edge.get("tgt_name"),
                "target_norm": edge.get("tgt_norm"),
                "keyword": edge.get("keyword"),
                "description": _join_descriptions(edge.get("descriptions")),
                "source_chunk_ids": list(edge.get("source_chunk_ids") or []),
            }
        )
        nb_norm = edge.get("nb_norm")
        if nb_norm and nb_norm not in neighbors:
            neighbors[nb_norm] = {
                "name": edge.get("nb_name"),
                "norm_name": nb_norm,
                "type": edge.get("nb_type"),
            }

    return {
        "name": record["name"],
        "norm_name": record["norm_name"],
        "type": record["type"],
        "descriptions": list(record["descriptions"] or []),
        "source_chunk_ids": list(record["source_chunk_ids"] or []),
        "neighbors": list(neighbors.values()),
        "edges": edges,
    }
