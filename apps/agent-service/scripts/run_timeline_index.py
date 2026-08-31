"""CLI BƯỚC 2/3: đọc units (đã verify ở bước 1) -> trích atomic event -> bảng `timeline_events`.

Tách khỏi bước 1 (phân đoạn) để chỉ trích trên units ĐÃ verify, không tự gom lại:
  BƯỚC 1  run_segmentation.py     : chunks -> dataset/timeline_units.json  (verify phân đoạn)
  BƯỚC 2  (đây)                   : timeline_units.json -> LLM trích -> reconcile -> Postgres
  BƯỚC 3  build_gazetteer.py      : gom location -> gazetteer để duyệt tọa độ thủ công

Pipeline bước này (giống run_graph_extraction.py, "vừa làm vừa check"):
  1. đọc units từ dataset/timeline_units.json (KHÔNG tự build — chạy run_segmentation.py trước)
  2. trích bằng LLM: 1 unit = 1 request, kết quả tách sẵn theo từng chunk trong unit
     -> cache `dataset/timeline_extractions.json` KHOÁ THEO chunk_id
  3. reconcile: gán event_id tất định + dedup xuyên chunk + parent_event_norm (THUẦN, không LLM)
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

Resume: cache khoá theo chunk_id, mỗi entry ghi kèm `prompt_version` + `unit_id`. Một unit
coi là XONG khi MỌI chunk của nó đã có entry khớp cả hai; thiếu một chunk -> trích lại TOÀN
unit và ghi đè. Sửa text mà giữ nguyên chunk_id -> phải bump `prompt_version` hoặc `--overwrite`
(cache không lưu hash nội dung).
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
    extract_unit_events,
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
    """Đọc cache trích. Cache format CŨ (khoá theo unit_id) -> ném lỗi, KHÔNG trộn.

    Cache cũ có `source_chunk_ids` trong entry và khoá ngoài cùng là `unit_id`; đọc lẫn
    vào luồng mới thì reconcile sẽ gán `source_chunk_ids = [unit_id]` -> provenance rác
    trong DB. Thà dừng và bắt đổi tên file còn hơn hỏng im lặng.
    """
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}

    legacy = [k for k, v in data.items() if isinstance(v, dict) and "source_chunk_ids" in v]
    if legacy:
        raise SystemExit(
            f"[cache] {path} là CACHE ĐỊNH DẠNG CŨ (khoá theo unit_id, có "
            f"'source_chunk_ids'; {len(legacy)} entry). Luồng mới khoá theo chunk_id.\n"
            f"  -> Đổi tên file cũ để giữ rollback rồi chạy lại, ví dụ:\n"
            f'     Rename-Item "{path}" "{path.stem}.unit-keyed.json"'
        )
    return data


def _write_artifact(path: Path, cache: dict[str, Any]) -> None:
    # Ghi atomic: file tạm cùng thư mục rồi os.replace (crash không hỏng cache).
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _unit_done(cache: dict[str, Any], unit: Unit) -> bool:
    """Unit XONG khi MỌI chunk của nó có entry khớp cả `prompt_version` lẫn `unit_id`."""
    for chunk_id in unit.chunk_ids:
        entry = cache.get(chunk_id)
        if not isinstance(entry, dict):
            return False
        if entry.get("prompt_version") != TIMELINE_PROMPT_VERSION:
            return False
        if entry.get("unit_id") != unit.unit_id:
            return False
    return True


def _summary(cache: dict[str, Any]) -> dict[str, int]:
    """Thống kê chất lượng tầng cache (trước dedup): phân loại event theo time/location."""
    events = [e for v in cache.values() for e in v.get("events", [])]
    return {
        "chunks": len(cache),
        "units": len({v.get("unit_id") for v in cache.values()}),
        "chunks_co_event": sum(1 for v in cache.values() if v.get("events")),
        "events": len(events),
        "co_time": sum(1 for e in events if e.get("time_start")),
        "co_location": sum(1 for e in events if e.get("locations")),
        "ca_hai": sum(1 for e in events if e.get("time_start") and e.get("locations")),
        "khong_ca_hai": sum(
            1 for e in events if not e.get("time_start") and not e.get("locations")
        ),
    }


def _show_units(cache: dict[str, Any], units: list[Unit], n: int) -> None:
    """In event của N unit đầu, TÁCH THEO CHUNK — soi việc quy event về đúng chunk."""
    for u in units[:n]:
        path = " > ".join(u.heading_path) or "(không heading)"
        total = sum(len(cache.get(cid, {}).get("events", [])) for cid in u.chunk_ids)
        print(f"\n=== UNIT {u.unit_id} | {path} | {total} sự kiện ===", flush=True)
        for i, chunk_id in enumerate(u.chunk_ids, start=1):
            entry = cache.get(chunk_id)
            if entry is None:
                print(f"  [ref={i}] {chunk_id}: (chưa trích)", flush=True)
                continue
            evs = entry.get("events", [])
            print(f"  [ref={i}] {chunk_id}: {len(evs)} sự kiện", flush=True)
            for e in evs:
                t = e.get("time_start") or "—"
                if e.get("time_end"):
                    t += f"..{e['time_end']}"
                loc = ", ".join(e.get("locations") or []) or "—"
                print(
                    f"      [{t}] ({e.get('confidence')}) {e.get('label')}\n"
                    f"          nơi: {loc} | parent: {e.get('parent_event') or '—'}",
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
    units: list[Unit]
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

    # Resume: unit xong khi MỌI chunk của nó đã có entry khớp version + unit_id.
    pending = units if args.overwrite else [u for u in units if not _unit_done(cache, u)]
    todo = pending[: args.limit] if args.limit > 0 else pending

    settings = get_settings()
    model = settings.timeline_llm_model or settings.llm_model
    src = "(cache, --limit<0)" if args.limit < 0 else f"{Path(args.units).name} (cap={cap})"
    print(
        f"Units: {src} | {len(units)} unit "
        f"({len(units) - len(pending)} đã trích, {len(todo)} sẽ xử lý lần này) | "
        f"model={model} | prompt={TIMELINE_PROMPT_VERSION} | {args.workers} luồng",
        flush=True,
    )

    errors: list[str] = []
    t0 = time.perf_counter()

    if todo:
        client = get_openai_client()

        def _process(unit: Unit) -> None:
            per_chunk = extract_unit_events(
                [(c.chunk_id, c.text) for c in unit.chunks],
                unit.heading_path,
                client=client,
                model=model,
            )
            # extract_unit_events bảo đảm phủ ĐỦ chunk của unit -> ghi trọn bộ, không
            # để sót entry cũ của unit nào khác (mỗi chunk chỉ thuộc đúng 1 unit).
            for chunk_id, events in per_chunk.items():
                cache[chunk_id] = {
                    "prompt_version": TIMELINE_PROMPT_VERSION,
                    "unit_id": unit.unit_id,
                    "events": [e.model_dump() for e in events],
                }

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
        _show_units(cache, units, args.show)
    print(f"\nCache -> {artifact_path}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
