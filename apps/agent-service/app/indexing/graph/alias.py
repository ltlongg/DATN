"""Resolve alias entity về tên canonical, dựa trên `dataset/alias_map.json`.

Tầng 2b: những trùng mà `normalize_name` (tầng 1+2a) không bắt được — typo, phiên
âm lệch ("Méccơnem"/"Méc-cơ-nen"), alias ngữ nghĩa ("Nguyễn Ái Quốc"->"Hồ Chí
Minh"). Map được dựng offline (LLM trọng tài) bởi `scripts/build_alias_map.py`.

`merge_graph` gọi `resolve()` TRƯỚC khi tạo khóa: biến thể -> dùng tên + norm_name
của canonical, nên các alias gom về một node khi index. Thiếu file map -> no-op
(trả về chính nó), pipeline vẫn chạy bình thường khi chưa dựng map.

Key của map là `norm_name` (đã qua normalize_name) để khớp bất kể hoa/thường/dấu.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.indexing.graph.normalize import normalize_name

__all__ = ["resolve", "load_alias_map", "alias_map_path"]

_REPO_ROOT = Path(__file__).resolve().parents[5]
_DEFAULT_MAP = _REPO_ROOT / "dataset" / "alias_map.json"


def alias_map_path() -> Path:
    return _DEFAULT_MAP


@lru_cache(maxsize=1)
def load_alias_map() -> dict[str, dict[str, str]]:
    """Đọc alias_map.json -> {variant_norm: {canonical_norm, canonical_name}}.

    Thiếu file -> {} (resolve thành no-op). Cache 1 lần; gọi `load_alias_map.cache_clear()`
    nếu cần nạp lại sau khi build map.
    """
    path = _DEFAULT_MAP
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("map", {})


def resolve(name: str) -> tuple[str, str]:
    """Trả (canonical_name hiển thị, canonical_norm khóa) cho một tên entity.

    Không phải alias -> (name, normalize_name(name)). Idempotent: canonical đã chuẩn
    nên resolve lần nữa không đổi.
    """
    norm = normalize_name(name)
    entry = load_alias_map().get(norm)
    if entry:
        return entry["canonical_name"], entry["canonical_norm"]
    return name, norm
