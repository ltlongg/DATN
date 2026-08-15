"""Grounding query-side: map mention/cụm trong câu hỏi -> node `:Entity` thật trong KG.

Đúng một việc: `ground(mention)` đi qua `resolve()` (normalize giữ dấu + tra alias_map) rồi
tra inverted-index `by_norm` -> đối xứng tuyệt đối với lúc index (`graph_store.merge_graph`
cũng resolve trước khi tạo khóa). KHÔNG bắn Cypher exact-match từng cụm.

Mention để ground đến từ ĐÚNG một nguồn: `entities` do node `plan` trích (đã qua guard ở
`orchestrator/planning.py`). Bản trước còn `token_match(query)` dò tên bằng cách tách chuỗi
query thành cụm rồi ground thử — đã XOÁ: nó chạy chính khi guard vừa loại sạch entity, tức
âm thầm gỡ lại đúng thứ guard vừa chặn, theo một luật không ai kiểm soát được.

Index nạp toàn bộ `norm_name`/`name`/`source_count` của `:Entity` từ Neo4j (KG nhỏ).
Cache ra `dataset/entity_index.json` kèm version stamp; rebuild khi `alias_map.json` hoặc
KG đổi — nếu không, sửa alias mà cache cũ sẽ ground về canonical CŨ (bug âm thầm).
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from neo4j import Driver

from app.indexing.graph.alias import alias_map_path, load_alias_map, resolve

__all__ = [
    "EntityInfo",
    "EntityIndex",
    "build_entity_index",
    "load_entity_index",
    "get_entity_index",
    "reset_entity_index_cache",
    "entity_index_path",
]

log = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[5]
_DEFAULT_CACHE = _REPO_ROOT / "dataset" / "entity_index.json"

# Cypher nạp toàn bộ entity (KG vài nghìn node). source_count = độ "hub" để guard.
_LOAD_ENTITIES = """
MATCH (e:Entity)
RETURN e.name AS name, e.norm_name AS norm_name,
       size(e.source_chunk_ids) AS source_count
"""
_COUNT_ENTITIES = "MATCH (e:Entity) RETURN count(e) AS n"

@dataclass(frozen=True)
class EntityInfo:
    """Một node `:Entity` rút gọn cho grounding."""

    name: str
    norm_name: str
    source_count: int

class EntityIndex:
    """Inverted-index `norm_name -> EntityInfo` + version stamp."""

    def __init__(
        self,
        by_norm: dict[str, EntityInfo],
        *,
        alias_map_version: str,
        kg_version: str,
    ) -> None:
        self.by_norm = by_norm
        self.alias_map_version = alias_map_version
        self.kg_version = kg_version

    @classmethod
    def from_entities(
        cls,
        entities: list[dict[str, Any]],
        *,
        alias_map_version: str,
        kg_version: str,
    ) -> EntityIndex:
        by_norm: dict[str, EntityInfo] = {}
        for e in entities:
            norm = e.get("norm_name")
            if not norm:
                continue
            by_norm[str(norm)] = EntityInfo(
                name=str(e.get("name") or norm),
                norm_name=str(norm),
                source_count=int(e.get("source_count") or 0),
            )
        return cls(
            by_norm,
            alias_map_version=alias_map_version,
            kg_version=kg_version,
        )

    def ground(self, mention: str) -> EntityInfo | None:
        """Map một mention -> EntityInfo qua resolve() (giữ dấu). None nếu không có node."""
        _, norm = resolve(mention)
        return self.by_norm.get(norm)

    def to_cache_dict(self) -> dict[str, Any]:
        return {
            "alias_map_version": self.alias_map_version,
            "kg_version": self.kg_version,
            "entities": [
                {"name": e.name, "norm_name": e.norm_name, "source_count": e.source_count}
                for e in self.by_norm.values()
            ],
        }

def entity_index_path() -> Path:
    return _DEFAULT_CACHE

def _alias_map_version() -> str:
    """Dấu hiệu alias_map đổi: mtime_ns + size của alias_map.json (rẻ, đủ phân biệt)."""
    path = alias_map_path()
    if not path.exists():
        return "none"
    st = path.stat()
    return f"{st.st_mtime_ns}:{st.st_size}"

def _kg_version(driver: Driver | None = None) -> str:
    """Dấu hiệu KG đổi: số node :Entity."""
    from app.core.neo4j import get_neo4j_driver

    driver = driver or get_neo4j_driver()
    with driver.session() as session:
        record = session.run(_COUNT_ENTITIES).single()
    return str(record["n"]) if record else "0"

def _current_versions(driver: Driver | None = None) -> dict[str, str]:
    return {
        "alias_map_version": _alias_map_version(),
        "kg_version": _kg_version(driver),
    }

def build_entity_index(driver: Driver | None = None) -> EntityIndex:
    """Nạp toàn bộ entity từ Neo4j -> EntityIndex (kèm version hiện tại)."""
    from app.core.neo4j import get_neo4j_driver

    # alias_map có thể vừa rebuild trong cùng process -> nạp lại để resolve dùng bản mới.
    load_alias_map.cache_clear()

    driver = driver or get_neo4j_driver()
    with driver.session() as session:
        rows = [dict(r) for r in session.run(_LOAD_ENTITIES)]
    versions = _current_versions(driver)
    log.info("Entity index: nạp %d node :Entity từ Neo4j.", len(rows))
    return EntityIndex.from_entities(
        rows,
        alias_map_version=versions["alias_map_version"],
        kg_version=versions["kg_version"],
    )

def _write_cache(cache_path: Path, index: EntityIndex) -> None:
    """Ghi cache atomic (os.replace) để không để lại file dở nếu lỗi giữa chừng."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = cache_path.with_suffix(cache_path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(index.to_cache_dict(), ensure_ascii=False), encoding="utf-8"
    )
    os.replace(tmp, cache_path)

def load_entity_index(
    *,
    driver: Driver | None = None,
    cache_path: Path | None = None,
) -> EntityIndex:
    """Load index từ cache nếu version khớp; lệch -> rebuild từ Neo4j + ghi đè cache.

    Cache lưu phần ĐẮT (toàn bộ node); version check chỉ tốn 1 COUNT query — vẫn rẻ hơn
    nạp lại mọi node mỗi lần khởi động.
    """
    cache_path = cache_path or _DEFAULT_CACHE
    current = _current_versions(driver)

    if cache_path.exists():
        try:
            data = json.loads(cache_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = None
        if (
            data
            and data.get("alias_map_version") == current["alias_map_version"]
            and data.get("kg_version") == current["kg_version"]
        ):
            return EntityIndex.from_entities(
                data.get("entities", []),
                alias_map_version=current["alias_map_version"],
                kg_version=current["kg_version"],
            )

    index = build_entity_index(driver=driver)
    _write_cache(cache_path, index)
    return index

@lru_cache(maxsize=1)
def get_entity_index() -> EntityIndex:
    """Index dùng chung trong process (graph retriever gọi mỗi câu hỏi)."""
    return load_entity_index()

def reset_entity_index_cache() -> None:
    """Xoá cache process (gọi sau khi re-index KG / rebuild alias trong cùng process)."""
    get_entity_index.cache_clear()
