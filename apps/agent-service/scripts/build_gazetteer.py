"""CLI: geocode địa danh trong `timeline_events` -> bảng `gazetteer` (+ review).

Pipeline:
  1. Đọc địa danh (surface form) + tần suất từ `timeline_events.locations`.
  2. Chuẩn hoá (normalize_name) -> gom nhóm theo location_norm, chọn surface phổ biến
     nhất làm display.
  3. Geocode mỗi địa danh: Google trước, LLM fallback (cache `dataset/gazetteer.json`).
  4. Upsert vào `gazetteer` (lat/lon None -> NULL: địa danh đó chỉ lên timeline).
  5. Sinh `dataset/gazetteer_review.md` để soát tay (ưu tiên confidence thấp / LLM).

`--min-count` chỉ geocode địa danh xuất hiện trong >= N event (bỏ nhiễu tần suất thấp).
Resume: location_norm đã có trong cache -> bỏ qua (trừ --overwrite). Gazetteer dùng
UPSERT (không TRUNCATE) nên chạy nhiều lần build dần, không sợ xoá trắng.

Ví dụ:
    python scripts/build_gazetteer.py --limit 5 --skip-db        # geocode thử 5 địa danh
    python scripts/build_gazetteer.py --workers 8                # geocode hết + nạp DB
    python scripts/build_gazetteer.py --min-count 2 --overwrite  # chỉ nơi >=2 event, làm lại
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import httpx

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)  # tắt log mỗi request Google

_THIS_DIR = Path(__file__).resolve().parent
_APP_ROOT = _THIS_DIR.parent
_REPO_ROOT = _THIS_DIR.parents[2]
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))

from app.core.config import get_settings  # noqa: E402
from app.core.llm import get_openai_client  # noqa: E402
from app.indexing.geocoding.geocoder import GEOCODE_PROMPT_VERSION, geocode_location  # noqa: E402
from app.indexing.graph.normalize import normalize_name  # noqa: E402
from app.schemas.gazetteer import GeocodeOutcome  # noqa: E402
from app.schemas.timeline import CONFIDENCE_RANK  # noqa: E402
from app.tools.visualization.event_store import select_location_counts  # noqa: E402
from app.tools.visualization.gazetteer_store import upsert_gazetteer  # noqa: E402

_CACHE = _REPO_ROOT / "dataset" / "gazetteer.json"
_REVIEW = _REPO_ROOT / "dataset" / "gazetteer_review.md"


def _load_cache(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _collect_locations(min_count: int) -> dict[str, dict[str, Any]]:
    """Đọc + gom địa danh theo location_norm. Trả {norm: {display, count}}."""
    counts = select_location_counts()
    groups: dict[str, dict[str, Any]] = {}
    for surface, n in counts.items():
        norm = normalize_name(surface)
        if not norm:
            continue
        g = groups.setdefault(norm, {"surfaces": Counter(), "count": 0})
        g["surfaces"][surface] += n
        g["count"] += n
    out: dict[str, dict[str, Any]] = {}
    for norm, g in groups.items():
        if g["count"] < min_count:
            continue
        display = g["surfaces"].most_common(1)[0][0]
        out[norm] = {"display": display, "count": g["count"]}
    return out


def _write_review(path: Path, cache: dict[str, Any]) -> None:
    """Sinh review.md: sắp confidence thấp + tần suất cao lên đầu để soát trước."""
    rows = sorted(
        cache.items(),
        key=lambda kv: (CONFIDENCE_RANK.get(kv[1].get("confidence"), 0), -kv[1].get("count", 0)),
    )
    lines = [
        "# Gazetteer review",
        "",
        f"Tổng {len(rows)} địa danh. Sắp theo confidence tăng dần + tần suất giảm dần "
        "(soát mấy dòng đầu trước). Sửa toạ độ sai trực tiếp trong `gazetteer.json` rồi "
        "chạy lại `build_gazetteer.py` (không cần --overwrite).",
        "",
        "| location_norm | display | lat | lon | conf | nguồn | #event | modern_name | note | provider |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for norm, v in rows:
        lat = "" if v.get("lat") is None else f"{v['lat']:.4f}"
        lon = "" if v.get("lon") is None else f"{v['lon']:.4f}"
        lines.append(
            f"| {norm} | {v.get('display','')} | {lat} | {lon} | {v.get('confidence','')} "
            f"| {v.get('resolved_by','')} | {v.get('count',0)} | {v.get('modern_name','')} "
            f"| {v.get('note','')} | {v.get('provider_name','')} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", default=str(_CACHE), help="Cache geocode (đọc + ghi).")
    parser.add_argument("--review", default=str(_REVIEW), help="File review markdown sinh ra.")
    parser.add_argument("--limit", type=int, default=0, help="Chỉ geocode N địa danh đầu chưa có. 0 = tất cả.")
    parser.add_argument("--workers", type=int, default=4, help="Số luồng geocode song song.")
    parser.add_argument("--min-count", type=int, default=1, help="Chỉ địa danh xuất hiện >= N event.")
    parser.add_argument("--overwrite", action="store_true", help="Geocode lại cả địa danh đã có cache.")
    parser.add_argument("--skip-db", action="store_true", help="Không upsert vào Postgres (chỉ cache + review).")
    args = parser.parse_args()

    cache_path = Path(args.cache)
    cache = _load_cache(cache_path)

    locations = _collect_locations(args.min_count)
    if not locations:
        print("Không có địa danh nào trong timeline_events (đã chạy run_timeline_index chưa?).", flush=True)
        return 0

    if args.overwrite:
        todo = dict(locations)
    else:
        todo = {norm: meta for norm, meta in locations.items() if norm not in cache}
    todo_items = list(todo.items())
    if args.limit > 0:
        todo_items = todo_items[: args.limit]

    settings = get_settings()
    has_google = bool(settings.google_maps_api_key)
    print(
        f"Địa danh: {len(locations)} (min-count={args.min_count}) | "
        f"{len(locations) - len(todo)} đã cache, {len(todo_items)} sẽ geocode | "
        f"Google={'có' if has_google else 'KHÔNG (chỉ LLM)'} | "
        f"model={settings.llm_model} | prompt={GEOCODE_PROMPT_VERSION} | {args.workers} luồng",
        flush=True,
    )

    errors: list[str] = []
    if todo_items:
        llm_client = get_openai_client()
        t0 = time.perf_counter()
        with httpx.Client() as http_client:
            def _process(item: tuple[str, dict[str, Any]]) -> tuple[str, GeocodeOutcome, dict[str, Any]]:
                norm, meta = item
                outcome = geocode_location(
                    meta["display"],
                    http_client=http_client,
                    client=llm_client,
                    model=settings.llm_model,
                )
                return norm, outcome, meta

            with ThreadPoolExecutor(max_workers=args.workers) as pool:
                futures = {pool.submit(_process, it): it[0] for it in todo_items}
                done_n = 0
                for fut in as_completed(futures):
                    norm = futures[fut]
                    try:
                        rnorm, outcome, meta = fut.result()
                        cache[rnorm] = {
                            "display": meta["display"],
                            "count": meta["count"],
                            **outcome.model_dump(),
                        }
                    except Exception as exc:  # noqa: BLE001
                        errors.append(f"{norm}: {type(exc).__name__}: {exc}")
                        print(f"    ! {norm}: {type(exc).__name__}: {' '.join(str(exc).split())[:300]}", flush=True)
                    done_n += 1
                    if done_n % 10 == 0 or done_n == len(todo_items):
                        print(f"  [{done_n}/{len(todo_items)}] lỗi={len(errors)}", flush=True)
                        _write_json(cache_path, cache)
        _write_json(cache_path, cache)
        print(f"Geocode xong trong {time.perf_counter() - t0:.1f}s.", flush=True)

    # Thống kê nguồn + sinh review.
    by_source = Counter(v.get("resolved_by", "none") for v in cache.values())
    located = sum(1 for v in cache.values() if v.get("lat") is not None)
    print(
        f"Cache: {len(cache)} địa danh | có toạ độ: {located} | "
        f"nguồn: {dict(by_source)}",
        flush=True,
    )
    _write_review(Path(args.review), cache)
    print(f"Review -> {args.review}", flush=True)

    if args.skip_db:
        print("[db] bỏ qua upsert gazetteer (--skip-db).", flush=True)
    else:
        records = [
            {
                "location_norm": norm,
                "display_name": v.get("display") or norm,
                "lat": v.get("lat"),
                "lon": v.get("lon"),
                "confidence": v.get("confidence") or "thấp",
            }
            for norm, v in cache.items()
        ]
        n = upsert_gazetteer(records)
        print(f"[db] Upsert {n} địa danh vào bảng gazetteer.", flush=True)

    if errors:
        print(f"[LỖI] {len(errors)} địa danh geocode thất bại (chạy lại sẽ thử tiếp).")
    print(f"Cache -> {args.cache}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
