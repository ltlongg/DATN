"""CLI BƯỚC 2/3: đọc units (đã verify ở bước 1) -> trích atomic event -> bảng `timeline_events`.

Tách khỏi bước 1 (phân đoạn) để chỉ trích trên units ĐÃ verify, không tự gom lại:
  BƯỚC 1  run_segmentation.py     : chunks -> dataset/timeline_units.json  (verify phân đoạn)
  BƯỚC 2  (đây)                   : timeline_units.json -> LLM trích -> reconcile -> Postgres
  BƯỚC 3  build_gazetteer.py      : timeline_events.locations -> gazetteer (lat/lon, để CUỐI)

Pipeline bước này (giống run_graph_extraction.py, "vừa làm vừa check"):
  1. đọc units từ dataset/timeline_units.json (KHÔNG tự build — chạy run_segmentation.py trước)
  2. trích bằng LLM (OpenAI Structured Outputs) -> cache `dataset/timeline_extractions.json`
  3. reconcile: gán event_id tất định + dedup xuyên unit + parent_event_norm (THUẦN, không LLM)
  4. load: TRUNCATE + insert trọn bộ vào Postgres `timeline_events`

`--limit` chỉ giới hạn bước TRÍCH lần này; reconcile + load luôn chạy trên TOÀN cache
(vì cache tích luỹ qua các lần resume, còn bảng DB nạp lại trọn bộ).

Mặc định: 4 luồng, xử lý theo LÔ 20 unit rồi DỪNG chờ Enter, Ctrl+C để dừng (đã lưu cache).

Ví dụ:
    # Soi nhanh section đầu, chưa đụng DB:
    python scripts/run_timeline_index.py --limit 2 --batch-size 0 --show 2 --skip-db

    # Trích hết + nạp DB, 8 luồng:
    python scripts/run_timeline_index.py --batch-size 0 --workers 8

    # Chỉ reconcile cache sẵn có rồi nạp DB (không gọi LLM, không cần units):
    python scripts/run_timeline_index.py --limit -1

Resume: mỗi unit trích xong lưu kèm `prompt_version`; lần sau bỏ qua unit có version khớp.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

_THIS_DIR = Path(__file__).resolve().parent
_APP_ROOT = _THIS_DIR.parent  # apps/agent-service
_REPO_ROOT = _THIS_DIR.parents[2]  # gốc repo
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))

from app.core.config import get_settings  # noqa: E402
from app.core.llm import get_openai_client  # noqa: E402
from app.indexing.timeline.atomic_event_extractor import (  # noqa: E402
    TIMELINE_PROMPT_VERSION,
    extract_timeline_events,
)
from app.indexing.timeline.reconcile import reconcile_events  # noqa: E402
from app.indexing.timeline.segmenter import Unit, unit_from_dict  # noqa: E402
from app.tools.visualization.event_store import replace_timeline_events  # noqa: E402

_DEFAULT_UNITS = _REPO_ROOT / "dataset" / "timeline_units.json"
_ARTIFACT = _REPO_ROOT / "dataset" / "timeline_extractions.json"


def _load_units(path: Path) -> tuple[int, list[Unit]]:
    """Đọc artifact units (do run_segmentation.py ghi) -> (cap, list[Unit])."""
    data = json.loads(path.read_text(encoding="utf-8"))
    cap = int(data.get("cap") or 0)
    units = [unit_from_dict(u) for u in (data.get("units") or [])]
    return cap, units


def _load_artifact(path: Path) -> dict[str, Any]:
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


def _write_artifact(path: Path, cache: dict[str, Any]) -> None:
    # Ghi atomic: file tạm cùng thư mục rồi os.replace (crash không hỏng cache).
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _summary(cache: dict[str, Any]) -> dict[str, int]:
    """Thống kê chất lượng tầng cache (trước dedup): phân loại event theo time/location."""
    events = [e for v in cache.values() for e in v.get("events", [])]
    has_t = sum(1 for e in events if e.get("time_start"))
    has_l = sum(1 for e in events if e.get("locations"))
    both = sum(1 for e in events if e.get("time_start") and e.get("locations"))
    neither = sum(1 for e in events if not e.get("time_start") and not e.get("locations"))
    return {
        "units": len(cache),
        "events": len(events),
        "co_time": has_t,
        "co_location": has_l,
        "ca_hai": both,
        "khong_ca_hai": neither,
    }


def _show_units(cache: dict[str, Any], unit_ids: list[str]) -> None:
    """In chi tiết event của vài unit để soi chất lượng bằng mắt."""
    for uid in unit_ids:
        entry = cache.get(uid)
        if not entry:
            continue
        path = " > ".join(entry.get("heading_path") or []) or "(không heading)"
        evs = entry.get("events", [])
        print(f"\n=== UNIT {uid} | {path} | {len(evs)} sự kiện ===", flush=True)
        for e in evs:
            t = e.get("time_start") or "—"
            if e.get("time_end"):
                t += f"..{e['time_end']}"
            loc = ", ".join(e.get("locations") or []) or "—"
            print(
                f"  [{t}] ({e.get('confidence')}) {e.get('label')}\n"
                f"      nơi: {loc} | parent: {e.get('parent_event') or '—'}",
                flush=True,
            )


def _batches(items: list[Unit], size: int) -> list[list[Unit]]:
    if size <= 0:
        return [items]
    return [items[i : i + size] for i in range(0, len(items), size)]


def _finalize(cache: dict[str, Any], args: argparse.Namespace) -> None:
    """Stage 3+4: reconcile cache -> records -> (tuỳ chọn) nạp Postgres."""
    if args.skip_reconcile:
        print("\n[reconcile] bỏ qua (--skip-reconcile).", flush=True)
        return

    records = reconcile_events(cache)
    cache_events = sum(len(v.get("events", [])) for v in cache.values())
    print(
        f"\n[reconcile] {cache_events} event (cache) -> {len(records)} event sau dedup "
        f"(theo event_id tất định).",
        flush=True,
    )

    if args.skip_db:
        print("[db] bỏ qua nạp Postgres (--skip-db).", flush=True)
        return
    # Chặn xoá trắng: replace_timeline_events TRUNCATE trước rồi insert. records rỗng
    # (cache thiếu/sai đường dẫn/hỏng JSON -> _load_artifact nuốt lỗi thành {}) sẽ wipe
    # cả bảng. Bắt buộc --allow-empty mới cho.
    if not records and not args.allow_empty:
        print(
            "[db] BỎ QUA nạp DB: 0 event sau reconcile (cache rỗng/sai --artifact/hỏng). "
            "Bảng timeline_events GIỮ NGUYÊN. Dùng --allow-empty nếu thực sự muốn xoá trắng.",
            flush=True,
        )
        return
    if args.limit > 0:
        print(
            "[db] CẢNH BÁO: --limit đang bật -> cache chỉ chứa phần đã trích, "
            "bảng timeline_events sẽ chỉ có bấy nhiêu (TRUNCATE + insert trọn bộ).",
            flush=True,
        )

    n = replace_timeline_events(records)
    print(f"[db] Đã nạp {n} event vào bảng timeline_events (TRUNCATE + insert).", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--units", default=str(_DEFAULT_UNITS), help="Artifact units (run_segmentation.py ghi).")
    parser.add_argument("--artifact", default=str(_ARTIFACT), help="Sổ cache timeline (đọc + ghi).")
    parser.add_argument(
        "--limit", type=int, default=0,
        help="Giới hạn bước TRÍCH: N unit đầu chưa trích. 0 = tất cả. <0 = không trích "
             "(chỉ reconcile + nạp DB từ cache sẵn có, không cần units).",
    )
    parser.add_argument("--workers", type=int, default=1, help="Số luồng gọi LLM song song.")
    parser.add_argument(
        "--batch-size", type=int, default=20,
        help="Xử lý theo lô N unit rồi DỪNG chờ Enter. 0 = chạy hết không dừng.",
    )
    parser.add_argument("--overwrite", action="store_true", help="Trích lại cả unit đã có trong cache.")
    parser.add_argument("--flush-every", type=int, default=10, help="Ghi cache sau mỗi N unit xong.")
    parser.add_argument("--show", type=int, default=0, help="In chi tiết event của N unit đầu sau khi xong.")
    parser.add_argument("--skip-reconcile", action="store_true", help="Chỉ trích + cache, không reconcile/DB.")
    parser.add_argument("--skip-db", action="store_true", help="Reconcile nhưng KHÔNG nạp Postgres.")
    parser.add_argument(
        "--allow-empty", action="store_true",
        help="Cho phép nạp DB khi reconcile ra 0 event (= XOÁ TRẮNG bảng). Mặc định CHẶN.",
    )
    args = parser.parse_args()

    artifact_path = Path(args.artifact)
    cache = _load_artifact(artifact_path)

    # --limit < 0: chỉ reconcile + nạp DB từ cache sẵn có -> KHÔNG cần units artifact.
    if args.limit < 0:
        cap, units = 0, []
    else:
        units_path = Path(args.units)
        if not units_path.exists():
            parser.error(
                f"Không tìm thấy {units_path}. Chạy BƯỚC 1 trước:\n"
                f"    python scripts/run_segmentation.py"
            )
        cap, units = _load_units(units_path)
        if not units:
            parser.error(f"{units_path} rỗng (0 unit). Chạy lại run_segmentation.py.")

    # Resume qua cache: unit có prompt_version khớp coi như xong (trừ --overwrite).
    if args.overwrite:
        done: set[str] = set()
    else:
        done = {
            uid for uid, v in cache.items()
            if v.get("prompt_version") == TIMELINE_PROMPT_VERSION
        }

    todo = [u for u in units if u.unit_id not in done]
    if args.limit > 0:
        todo = todo[: args.limit]

    settings = get_settings()
    model = settings.timeline_llm_model or settings.llm_model
    src = "(cache, --limit<0)" if args.limit < 0 else f"{Path(args.units).name} (cap={cap})"
    print(
        f"Units: {src} | {len(units)} unit "
        f"({len(done)} đã trích, {len(todo)} sẽ xử lý) | "
        f"model={model} | prompt={TIMELINE_PROMPT_VERSION} | {args.workers} luồng",
        flush=True,
    )

    errors: list[str] = []
    t0 = time.perf_counter()

    if todo:
        client = get_openai_client()

        def _process(unit: Unit) -> str:
            result = extract_timeline_events(
                unit.text,
                unit.heading_path,
                client=client,
                model=model,
                unit_id=unit.unit_id,
            )
            cache[unit.unit_id] = {
                "prompt_version": TIMELINE_PROMPT_VERSION,
                "heading_path": unit.heading_path,
                "source_chunk_ids": unit.source_chunk_ids,
                "events": [e.model_dump() for e in result.events],
            }
            return unit.unit_id

        total = len(todo)
        completed = 0
        log_every = max(1, total // 20)
        batches = _batches(todo, args.batch_size)
        for bi, batch in enumerate(batches):
            with ThreadPoolExecutor(max_workers=args.workers) as pool:
                futures = {pool.submit(_process, u): u.unit_id for u in batch}
                for fut in as_completed(futures):
                    uid = futures[fut]
                    try:
                        fut.result()
                    except Exception as exc:  # noqa: BLE001 - đếm lỗi, không vào cache -> resume thử lại
                        errors.append(f"{uid}: {type(exc).__name__}: {exc}")
                        msg = " ".join(str(exc).split())
                        print(f"    ! {uid}: {type(exc).__name__}: {msg[:500]}", flush=True)
                    completed += 1
                    if completed % log_every == 0 or completed == total:
                        pct = completed * 100 // total if total else 100
                        print(f"  [{completed:4d}/{total} {pct:3d}%] lỗi={len(errors)}", flush=True)
                    if completed % args.flush_every == 0:
                        _write_artifact(artifact_path, cache)
            _write_artifact(artifact_path, cache)  # chốt cache sau mỗi lô

            if args.batch_size > 0 and bi < len(batches) - 1:
                s = _summary(cache)
                print(
                    f"\n>>> Xong lô {bi + 1}/{len(batches)}: {completed}/{total} unit "
                    f"(cache: {s['events']} sự kiện, lỗi={len(errors)}). Đã ghi {artifact_path}.",
                    flush=True,
                )
                if not sys.stdin.isatty():
                    print(">>> (stdin không tương tác -> chạy tiếp tự động)", flush=True)
                    continue
                try:
                    input(">>> Kiểm tra xong, nhấn Enter để chạy lô tiếp (Ctrl+C để dừng)... ")
                except (EOFError, KeyboardInterrupt):
                    print("\nDừng theo yêu cầu. Cache đã lưu — bỏ qua reconcile/DB lần này.", flush=True)
                    print(f"Cache -> {artifact_path}")
                    return 0
    else:
        print("Không có unit cần trích lần này.", flush=True)

    elapsed = time.perf_counter() - t0
    print(f"\nTrích xong trong {elapsed:.1f}s.", json.dumps(_summary(cache), ensure_ascii=False))
    if errors:
        print(f"[LỖI] {len(errors)} unit thất bại (sẽ thử lại lần sau):")
        for e in errors[:10]:
            print("  -", e)

    _finalize(cache, args)

    if args.show > 0:
        _show_units(cache, [u.unit_id for u in units[: args.show]])
    print(f"\nCache -> {artifact_path}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
