"""Xóa sạch dataset ở Postgres + Qdrant + Neo4j để index lại từ đầu.

Dùng lại các client đã cấu hình trong app.core (tránh lặp bẫy https=False của Qdrant,
+psycopg của DATABASE_URL). Mặc định CHỈ in preview; phải truyền --yes mới xóa thật.

Xóa gì:
  - Postgres: DROP TABLE rag_chunks (schema sẽ được ensure_rag_chunks_table tạo lại khi index).
  - Qdrant:   delete collection history_vn_chunks (ensure_chunks_collection tạo lại khi index).
  - Neo4j:    MATCH (n) DETACH DELETE n — xóa toàn bộ node/relationship (DB này dành riêng cho KG).
  - --cache:  thêm cờ này để xóa luôn dataset/graph_extractions.json (sổ resume trích LLM).

Ví dụ (PowerShell):
    $env:PYTHONIOENCODING="utf-8"
    cd apps/agent-service
    ..\..\venv\Scripts\python.exe scripts/reset_stores.py            # preview
    ..\..\venv\Scripts\python.exe scripts/reset_stores.py --yes      # xóa 3 store
    ..\..\venv\Scripts\python.exe scripts/reset_stores.py --yes --cache
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

_AGENT_SERVICE = Path(__file__).resolve().parents[1]
if str(_AGENT_SERVICE) not in sys.path:
    sys.path.insert(0, str(_AGENT_SERVICE))

_REPO_ROOT = _AGENT_SERVICE.parents[1]
_ARTIFACT = _REPO_ROOT / "dataset" / "graph_extractions.json"

import psycopg  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.tools.graph_rag.chunk_store import _database_url  # noqa: E402


def reset_postgres() -> None:
    with psycopg.connect(_database_url()) as conn:
        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS rag_chunks;")
        conn.commit()
    print("[postgres] DROP TABLE rag_chunks — xong.")


def reset_qdrant() -> None:
    from app.core.qdrant import get_qdrant_client

    name = get_settings().qdrant_collection
    client = get_qdrant_client()
    if client.collection_exists(name):
        client.delete_collection(name)
        print(f"[qdrant]   delete collection {name} — xong.")
    else:
        print(f"[qdrant]   collection {name} không tồn tại — bỏ qua.")


def reset_neo4j() -> None:
    from app.core.neo4j import get_neo4j_driver

    driver = get_neo4j_driver()
    try:
        with driver.session() as session:
            summary = session.run("MATCH (n) DETACH DELETE n").consume()
        c = summary.counters
        print(
            f"[neo4j]    DETACH DELETE — xóa {c.nodes_deleted} node, "
            f"{c.relationships_deleted} relationship."
        )
    finally:
        driver.close()


def reset_cache() -> None:
    if _ARTIFACT.exists():
        _ARTIFACT.unlink()
        print(f"[cache]    xóa {_ARTIFACT} — xong.")
    else:
        print(f"[cache]    {_ARTIFACT} không tồn tại — bỏ qua.")


def main() -> None:
    p = argparse.ArgumentParser(description="Reset dataset ở Postgres + Qdrant + Neo4j.")
    p.add_argument("--yes", action="store_true", help="Xác nhận xóa thật (không có cờ này = preview).")
    p.add_argument("--cache", action="store_true", help="Xóa luôn dataset/graph_extractions.json.")
    args = p.parse_args()

    s = get_settings()
    print("Sẽ xóa:")
    print(f"  - Postgres : bảng rag_chunks  @ {s.database_url or '(thiếu DATABASE_URL)'}")
    print(f"  - Qdrant   : collection {s.qdrant_collection}  @ {s.qdrant_host}:{s.qdrant_port}")
    print(f"  - Neo4j    : toàn bộ node/relationship  @ {s.neo4j_uri or '(thiếu NEO4J_URI)'}")
    if args.cache:
        print(f"  - Cache    : {_ARTIFACT}")
    print()

    if not args.yes:
        print("PREVIEW — chưa xóa gì. Thêm --yes để thực thi.")
        return

    reset_postgres()
    reset_qdrant()
    reset_neo4j()
    if args.cache:
        reset_cache()
    print("\nHoàn tất reset. Chạy lại scripts/run_graph_index.py để index từ đầu.")


if __name__ == "__main__":
    main()
