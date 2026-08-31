"""Gom địa danh từ artifact timeline vào `dataset/gazetteer.json`, không gọi API hay LLM.

Script chỉ liệt kê địa danh + đếm số lần xuất hiện, giữ nguyên `lat`/`lon` đã điền tay
từ lần chạy trước. Toạ độ tra bằng `scripts/latlon_check.html` (mở thẳng bằng trình
duyệt) rồi điền vào file JSON này; `--sync-db` đẩy sang Postgres cho marker sản phẩm.

Ví dụ:
    python scripts/build_gazetteer.py
    python scripts/build_gazetteer.py --artifact dataset/timeline_extractions_tap2_3_va_wiki.json
    python scripts/build_gazetteer.py --sync-db
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_THIS_DIR = Path(__file__).resolve().parent
_APP_ROOT = _THIS_DIR.parent
_REPO_ROOT = _THIS_DIR.parents[2]
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))

from app.indexing.graph.normalize import normalize_name  # noqa: E402
from app.schemas.gazetteer import GazetteerEntry  # noqa: E402

_GAZETTEER = _REPO_ROOT / "dataset" / "gazetteer.json"


def _load_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return {}
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"{path} phải là JSON object")
    return data


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _discover_artifacts(explicit: list[str] | None) -> list[Path]:
    if explicit:
        paths = [Path(value).resolve() for value in explicit]
    else:
        paths = sorted((_REPO_ROOT / "dataset").glob("timeline_extractions*.json"))
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError("Không tìm thấy artifact: " + ", ".join(missing))
    if not paths:
        raise FileNotFoundError("Không có dataset/timeline_extractions*.json")
    return paths


def collect_locations(paths: list[Path], min_count: int = 1) -> dict[str, dict[str, Any]]:
    """Gom location từ event theo tên chuẩn hóa, chọn surface xuất hiện nhiều nhất."""
    groups: dict[str, dict[str, Any]] = {}
    for path in paths:
        artifact = _load_object(path)
        for entry in artifact.values():
            if not isinstance(entry, dict):
                continue
            for event in entry.get("events") or []:
                if not isinstance(event, dict):
                    continue
                for surface in event.get("locations") or []:
                    if not isinstance(surface, str):
                        continue
                    norm = normalize_name(surface)
                    if not norm:
                        continue
                    group = groups.setdefault(norm, {"surfaces": Counter(), "count": 0})
                    group["surfaces"][surface] += 1
                    group["count"] += 1

    result: dict[str, dict[str, Any]] = {}
    for norm, group in groups.items():
        count = int(group["count"])
        if count >= min_count:
            result[norm] = {
                "display": group["surfaces"].most_common(1)[0][0],
                "count": count,
            }
    return result


def clean_entry(raw: object, *, display: str, count: int) -> dict[str, Any]:
    """Đưa mục cũ về schema hiện tại, giữ nguyên lat/lon đã điền tay.

    Mục sinh từ pipeline geocode cũ còn thừa `status`/`confidence`/`resolved_by`; các
    field đó bị bỏ, chỉ toạ độ và ghi chú sống tiếp.
    """
    value = raw if isinstance(raw, dict) else {}
    return GazetteerEntry(
        display=str(value.get("display") or display),
        count=count,
        lat=value.get("lat") if isinstance(value.get("lat"), (int, float)) else None,
        lon=value.get("lon") if isinstance(value.get("lon"), (int, float)) else None,
        note=str(value.get("note") or ""),
    ).model_dump()


def merge_gazetteer(
    existing: dict[str, Any], locations: dict[str, dict[str, Any]], *, prune: bool = False
) -> dict[str, Any]:
    keys = set(locations) if prune else set(existing) | set(locations)
    merged: dict[str, Any] = {}
    for norm in sorted(keys, key=lambda key: (-int(locations.get(key, {}).get("count", 0)), key)):
        current = existing.get(norm)
        meta = locations.get(norm) or {}
        old = current if isinstance(current, dict) else {}
        display = str(meta.get("display") or old.get("display") or norm)
        count = int(meta.get("count", old.get("count", 0)) or 0)
        merged[norm] = clean_entry(current, display=display, count=count)
    return merged


def _db_records(gazetteer: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "location_norm": norm,
            "display_name": value["display"],
            "lat": value.get("lat"),
            "lon": value.get("lon"),
            "note": value.get("note") or "",
        }
        for norm, value in gazetteer.items()
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", action="append", help="Artifact timeline; lặp lại được.")
    parser.add_argument("--gazetteer", default=str(_GAZETTEER), help="File JSON đọc và ghi.")
    parser.add_argument("--min-count", type=int, default=1, help="Chỉ thêm nơi xuất hiện ít nhất N lần.")
    parser.add_argument("--prune", action="store_true", help="Bỏ mục không còn trong artifact đầu vào.")
    parser.add_argument("--sync-db", action="store_true", help="Đẩy toạ độ đã điền tay sang PostgreSQL.")
    args = parser.parse_args()

    artifacts = _discover_artifacts(args.artifact)
    locations = collect_locations(artifacts, max(1, args.min_count))
    path = Path(args.gazetteer)
    existing = _load_object(path)
    merged = merge_gazetteer(existing, locations, prune=args.prune)
    _write_json(path, merged)

    placed = sum(1 for value in merged.values() if value["lat"] is not None and value["lon"] is not None)
    print(f"Artifact: {', '.join(p.name for p in artifacts)}")
    print(f"Gazetteer: {len(merged)} địa danh | {placed} đã có toạ độ, {len(merged) - placed} còn trống")
    print(f"Đã ghi: {path}")

    if args.sync_db:
        from app.tools.visualization.gazetteer_store import upsert_gazetteer

        n = upsert_gazetteer(_db_records(merged))
        print(f"Đã đồng bộ {n} địa danh vào PostgreSQL.")
    else:
        print("Chưa ghi DB. Điền lat/lon vào file rồi chạy lại với --sync-db để lên marker.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
