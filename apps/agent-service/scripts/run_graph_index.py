"""Index chunk vào Postgres + Qdrant + Neo4j (pipeline DIY, không LightRAG).

Đọc `dataset/chunks_llm.json` (đã chia sẵn bằng Chonkie + đã trích metadata), chuẩn
hóa record rồi:
  1. Upsert Postgres `rag_chunks` (source of truth: text + full metadata).
  2. Embed `embedding_text` -> upsert Qdrant `history_vn_chunks` (vector + payload tối giản).
  3. Trích entity/quan hệ (song song) -> cache `dataset/graph_extractions.json` -> merge Neo4j.

`chunk_id` là khóa nối duy nhất xuyên Postgres/Qdrant/Neo4j. Bước (3) tốn LLM nên kết
quả được cache ra artifact (vừa để inspect, vừa làm sổ resume theo prompt_version); chỉ
chunk mới trích mới được merge vào Neo4j (trừ khi --remerge). Merge idempotent nên
re-merge an toàn.

Ràng buộc: embed (asyncio.run) ở main thread, NGOÀI ThreadPoolExecutor của graph pass.

Ví dụ (PowerShell):
    $env:PYTHONIOENCODING="utf-8"
    cd apps/agent-service
    ..\..\venv\Scripts\python.exe scripts/run_graph_index.py --limit 5
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

_AGENT_SERVICE = Path(__file__).resolve().parents[1]
if str(_AGENT_SERVICE) not in sys.path:
    sys.path.insert(0, str(_AGENT_SERVICE))

_REPO_ROOT = _AGENT_SERVICE.parents[1]
_ARTIFACT = _REPO_ROOT / "dataset" / "graph_extractions.json"

from app.tools.graph_rag.chunk_store import upsert_rag_chunks  # noqa: E402
from app.tools.graph_rag.chunks import prepare_chunk_records  # noqa: E402
from app.tools.graph_rag.vector_store import upsert_chunk_vectors  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("graph_index")

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Index chunk vào Postgres + Qdrant + Neo4j.")
    p.add_argument("--file", default=str(_REPO_ROOT / "dataset" / "chunks_llm.json"))
    p.add_argument("--limit", type=int, default=100, help="Chỉ index N chunk đầu (0 = tất cả).")
    p.add_argument("--batch-size", type=int, default=128, help="Batch embed/upsert Qdrant.")
    p.add_argument("--workers", type=int, default=4, help="Số luồng trích graph song song.")
    p.add_argument("--flush-every", type=int, default=50, help="Ghi artifact mỗi N chunk trích.")
    p.add_argument("--overwrite", action="store_true", help="Trích lại cả chunk đã có trong cache.")
    p.add_argument("--remerge", action="store_true", help="Merge lại Neo4j cả chunk lấy từ cache.")
    p.add_argument("--skip-vectors", action="store_true", help="Bỏ qua bước Qdrant.")
    p.add_argument("--skip-graph", action="store_true", help="Bỏ qua bước Neo4j graph.")
    return p.parse_args()

def _load_chunks(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{path} không phải JSON list.")
    return data

def _load_artifact(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}

def _write_artifact(path: Path, cache: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)

def _run_graph(records: list[dict], args: argparse.Namespace) -> None:
    from app.core.neo4j import ensure_graph_constraints, get_neo4j_driver
    from app.indexing.graph.entity_relation_extractor import (
        GRAPH_PROMPT_VERSION,
        extract_graph,
    )
    from app.schemas.graph import GraphExtraction
    from app.tools.graph_rag.graph_store import merge_graph

    cache = _load_artifact(_ARTIFACT)

    # Chunk cần trích: chưa có trong cache hoặc prompt_version khác (trừ khi --overwrite).
    to_extract = [
        r
        for r in records
        if args.overwrite
        or cache.get(r["chunk_id"], {}).get("prompt_version") != GRAPH_PROMPT_VERSION
    ]
    log.info(
        "Trích graph prompt=%s: %d cần trích, %d dùng cache",
        GRAPH_PROMPT_VERSION,
        len(to_extract),
        len(records) - len(to_extract),
    )

    newly: list[str] = []
    errors = 0
    if to_extract:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {
                pool.submit(
                    extract_graph,
                    r["text"],
                    chunk_id=r["chunk_id"],
                ): r
                for r in to_extract
            }
            for fut in as_completed(futures):
                cid = futures[fut]["chunk_id"]
                try:
                    result = fut.result()
                except Exception as exc:  # noqa: BLE001 — đếm lỗi, không mark done -> retry lần sau
                    errors += 1
                    log.warning("Trích lỗi chunk %s: %s", cid, exc)
                    continue
                cache[cid] = {
                    "prompt_version": GRAPH_PROMPT_VERSION,
                    "entities": [e.model_dump() for e in result.entities],
                    "relations": [rel.model_dump() for rel in result.relations],
                }
                newly.append(cid)
                if len(newly) % args.flush_every == 0:
                    _write_artifact(_ARTIFACT, cache)
                    log.info("Trích graph: %d/%d", len(newly), len(to_extract))
        _write_artifact(_ARTIFACT, cache)
    log.info("Trích xong: %d mới, %d lỗi. Artifact: %s", len(newly), errors, _ARTIFACT)

    # Merge Neo4j.
    ensure_graph_constraints()
    driver = get_neo4j_driver()
    merge_ids = [r["chunk_id"] for r in records] if args.remerge else newly
    n_ent = n_rel = 0
    try:
        for cid in merge_ids:
            entry = cache.get(cid)
            if not entry:
                continue
            extraction = GraphExtraction.model_validate(
                {"entities": entry["entities"], "relations": entry["relations"]}
            )
            stats = merge_graph(cid, extraction, driver=driver)
            n_ent += stats["entities"]
            n_rel += stats["relations"]
    finally:
        driver.close()
    log.info("Merge Neo4j: %d entity, %d relation từ %d chunk", n_ent, n_rel, len(merge_ids))

def main() -> None:
    args = _parse_args()
    chunks = _load_chunks(Path(args.file))
    subset = chunks[: args.limit] if args.limit else chunks
    records = prepare_chunk_records(subset)
    log.info("Chuẩn hóa %d/%d chunk", len(records), len(chunks))

    # 1) Postgres source of truth.
    upserted = upsert_rag_chunks(records)
    log.info("Upsert Postgres rag_chunks: %d", upserted)

    # 2) Qdrant vector (main thread — embed dùng asyncio.run).
    if args.skip_vectors:
        log.info("Bỏ qua Qdrant (--skip-vectors).")
    else:
        from app.core.qdrant import ensure_chunks_collection

        ensure_chunks_collection()
        n_vec = upsert_chunk_vectors(records, batch_size=args.batch_size)
        log.info("Upsert Qdrant: %d point", n_vec)

    # 3) Neo4j graph.
    if args.skip_graph:
        log.info("Bỏ qua Neo4j graph (--skip-graph).")
    else:
        _run_graph(records, args)

    log.info("Xong.")

if __name__ == "__main__":
    main()
