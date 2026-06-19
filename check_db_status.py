"""Check trạng thái Postgres / Qdrant / Neo4j sau khi chạy run_graph_index."""
import sys
from pathlib import Path

_AGENT = Path(__file__).resolve().parent / "apps" / "agent-service"
sys.path.insert(0, str(_AGENT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.core.config import get_settings

s = get_settings()

# ---------- Postgres ----------
print("=" * 50)
print("POSTGRES (rag_chunks)")
print("=" * 50)
try:
    import psycopg
    url = s.database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('rag_chunks')")
            exists = cur.fetchone()[0]
            if not exists:
                print("  Bảng rag_chunks CHƯA tồn tại.")
            else:
                cur.execute("SELECT count(*) FROM rag_chunks")
                print(f"  rag_chunks: {cur.fetchone()[0]} rows")
                cur.execute("SELECT chunk_id FROM rag_chunks ORDER BY chunk_id LIMIT 1")
                r = cur.fetchone()
                print(f"  first chunk_id: {r[0] if r else None}")
except Exception as e:
    print(f"  LỖI: {type(e).__name__}: {e}")

# ---------- Qdrant ----------
print("=" * 50)
print("QDRANT")
print("=" * 50)
try:
    from app.core.qdrant import get_qdrant_client
    client = get_qdrant_client()
    cols = [c.name for c in client.get_collections().collections]
    print(f"  collections: {cols}")
    if s.qdrant_collection in cols:
        info = client.get_collection(s.qdrant_collection)
        print(f"  '{s.qdrant_collection}': {info.points_count} points, "
              f"vector_size={info.config.params.vectors.size}")
    else:
        print(f"  Collection '{s.qdrant_collection}' CHƯA tồn tại.")
except Exception as e:
    print(f"  LỖI: {type(e).__name__}: {e}")

# ---------- Neo4j ----------
print("=" * 50)
print("NEO4J")
print("=" * 50)
try:
    from app.core.neo4j import get_neo4j_driver
    driver = get_neo4j_driver()
    with driver.session() as sess:
        n_ent = sess.run("MATCH (e:Entity) RETURN count(e) AS c").single()["c"]
        n_rel = sess.run("MATCH ()-[r:REL]->() RETURN count(r) AS c").single()["c"]
        print(f"  :Entity nodes: {n_ent}")
        print(f"  :REL relationships: {n_rel}")
        rows = sess.run(
            "MATCH (e:Entity) RETURN e.name AS name LIMIT 5"
        ).data()
        print(f"  sample entities: {[x['name'] for x in rows]}")
    driver.close()
except Exception as e:
    print(f"  LỖI: {type(e).__name__}: {e}")

print("=" * 50)
