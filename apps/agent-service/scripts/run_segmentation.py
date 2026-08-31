"""CLI BƯỚC 1/3 (offline): gom chunk -> unit (segmenter), ghi artifact + report để VERIFY.

Tách khỏi run_timeline_index.py (bước 2 - LLM) để SOI KỸ ranh giới phân đoạn TRƯỚC khi
tốn token LLM. Luồng offline 3 bước rời, chạy & verify độc lập:
  1. (đây) run_segmentation.py : chunks_llm.json -> dataset/timeline_units.json   [VERIFY ở đây]
  2. run_timeline_index.py     : đọc timeline_units.json -> LLM trích -> timeline_events
  3. build_gazetteer.py        : gom location -> gazetteer để duyệt tọa độ thủ công

THUẦN, không LLM, tất định: cùng chunks + cùng cap -> cùng units (idempotent).

INVARIANT (chốt chặn): mỗi chunk hợp lệ phải nằm trong ĐÚNG MỘT unit. Vỡ invariant ->
KHÔNG ghi artifact, thoát mã 1: bước 2 cache theo chunk_id nên một chunk ở 2 unit sẽ bị
hai lần gọi LLM ghi đè lẫn nhau (mất event im lặng).

Ví dụ:
    python scripts/run_segmentation.py                       # sinh units + report tổng quan
    python scripts/run_segmentation.py --cap 40000 --list -1 # cap khác, liệt kê hết unit
    python scripts/run_segmentation.py --show 3              # in FULL text 3 unit đầu để đọc kỹ
    python scripts/run_segmentation.py --report-only         # chỉ đọc artifact, in lại report
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from collections import Counter
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

_THIS_DIR = Path(__file__).resolve().parent
_APP_ROOT = _THIS_DIR.parent  # apps/agent-service
_REPO_ROOT = _THIS_DIR.parents[2]  # gốc repo
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))

from app.indexing.timeline.segmenter import (  # noqa: E402
    CAP_CHARS,
    Unit,
    build_units,
    unit_from_dict,
    unit_to_dict,
)

_DEFAULT_CHUNKS = _REPO_ROOT / "dataset" / "chunks_llm.json"
_DEFAULT_UNITS = _REPO_ROOT / "dataset" / "timeline_units.json"

def _valid_input_ids(chunks: list[dict]) -> list[str]:
    """ID các chunk segmenter THỰC SỰ xét (có id + text không rỗng) — khớp _prepare()."""
    out: list[str] = []
    for c in chunks:
        cid = c.get("chunk_id")
        text = c.get("text") or ""
        if cid and text.strip():
            out.append(str(cid))
    return out

def _write_units(path: Path, cap: int, source: str, units: list[Unit]) -> None:
    """Ghi atomic artifact units (envelope kèm cap + nguồn để bước 2 đọc lại)."""
    payload = {
        "cap": cap,
        "source_file": source,
        "count": len(units),
        "units": [unit_to_dict(u) for u in units],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)

def _check_invariant(units: list[Unit], input_ids: list[str] | None) -> list[str]:
    """Kiểm tra "mỗi chunk đúng một unit". Trả danh sách vi phạm (rỗng = đạt)."""
    usage = Counter(cid for u in units for cid in u.chunk_ids)
    problems = [f"chunk {cid} nằm ở {k} unit (phải = 1)" for cid, k in sorted(usage.items()) if k > 1]
    if input_ids is not None:
        missing = sorted(set(input_ids) - set(usage))
        extra = sorted(set(usage) - set(input_ids))
        problems += [f"chunk {cid} KHÔNG vào unit nào" for cid in missing]
        problems += [f"chunk {cid} LẠ (không có trong nguồn)" for cid in extra]
    return problems

def _report(units: list[Unit], cap: int, input_ids: list[str] | None) -> None:
    """Report kiểm tra phân đoạn: phủ chunk, overlap, phân bố độ dài, unit vượt cap."""
    n = len(units)
    if n == 0:
        print("(0 unit)", flush=True)
        return
    lens = sorted(u.char_len for u in units)
    usage = Counter(cid for u in units for cid in u.chunk_ids)
    oversize = [u for u in units if u.char_len > cap]

    print(f"\n=== REPORT phân đoạn: {n} unit (cap={cap:,}) ===", flush=True)
    print(
        f"  độ dài (ký tự): min {lens[0]:,} | median {int(statistics.median(lens)):,}"
        f" | max {lens[-1]:,}",
        flush=True,
    )
    print(f"  chunk/unit: min {min(len(u.chunks) for u in units)} | max {max(len(u.chunks) for u in units)}", flush=True)
    print(
        f"  unit VƯỢT cap (chunk đơn lẻ quá dài, giữ nguyên vẹn): {len(oversize)}",
        flush=True,
    )
    print(
        f"  chunk dùng lại ở >1 unit (overlap — BẮT BUỘC = 0): "
        f"{sum(1 for k in usage.values() if k > 1)}",
        flush=True,
    )

    if input_ids is not None:
        input_set = set(input_ids)
        status = "ĐỦ" if input_set <= set(usage) else f"THIẾU {len(input_set - set(usage))}"
        print(
            f"  phủ chunk: {len(input_set)} chunk nguồn -> phủ "
            f"{len(set(usage) & input_set)} ({status})",
            flush=True,
        )

    if oversize:
        print("\n  -- unit vượt cap cần soi kỹ --", flush=True)
        for u in oversize:
            path = " > ".join(u.heading_path) or "(không heading)"
            print(f"    {u.char_len:>7,} chữ | {u.unit_id} | {path}", flush=True)

def _list_units(units: list[Unit], cap: int, limit: int) -> None:
    """Liệt kê unit theo THỨ TỰ VĂN BẢN (dòng tóm tắt) để soi ranh giới tuần tự."""
    shown = units if limit < 0 else units[:limit]
    print(f"\n--- liệt kê {len(shown)}/{len(units)} unit (thứ tự văn bản) ---", flush=True)
    for i, u in enumerate(shown):
        path = " > ".join(u.heading_path) or "(không heading)"
        flag = " ⚠vượt-cap" if u.char_len > cap else ""
        print(
            f"  [{i:3d}] {u.char_len:>7,}c {len(u.chunks):>3} chunk | "
            f"{u.unit_id}{flag}\n        {path}",
            flush=True,
        )

def _show_full(units: list[Unit], n: int) -> None:
    """In FULL text n unit đầu, TÁCH THEO CHUNK — đúng dạng LLM sẽ nhận ở bước 2."""
    for u in units[:n]:
        path = " > ".join(u.heading_path) or "(không heading)"
        bar = "=" * 70
        print(
            f"\n{bar}\nUNIT {u.unit_id} | {path} | {u.char_len:,} chữ | {len(u.chunks)} chunk",
            flush=True,
        )
        for i, c in enumerate(u.chunks, start=1):
            print(f"{'-' * 70}\n[ref={i}] {c.chunk_id} ({len(c.text):,} chữ)\n{c.text}", flush=True)

def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--file", default=str(_DEFAULT_CHUNKS), help="File chunks JSON nguồn.")
    parser.add_argument("--out", default=str(_DEFAULT_UNITS), help="Artifact units để ghi (bước 2 đọc lại).")
    parser.add_argument("--cap", type=int, default=CAP_CHARS, help=f"Cap ký tự mỗi unit (mặc định {CAP_CHARS}).")
    parser.add_argument("--list", type=int, default=0, help="Liệt kê unit (dòng tóm tắt): 0 = không, N = N đầu, -1 = tất cả.")
    parser.add_argument("--show", type=int, default=0, help="In FULL text N unit đầu (tách theo chunk) để đọc kỹ.")
    parser.add_argument("--report-only", action="store_true", help="Chỉ đọc --out in lại report, KHÔNG build.")
    args = parser.parse_args()

    out_path = Path(args.out)

    if args.report_only:
        if not out_path.exists():
            parser.error(f"Không có {out_path} để --report-only. Bỏ cờ này để build trước.")
        data = json.loads(out_path.read_text(encoding="utf-8"))
        units = [unit_from_dict(u) for u in (data.get("units") or [])]
        cap = int(data.get("cap") or args.cap)
        print(f"Đọc {out_path.name}: {len(units)} unit (cap={cap}).", flush=True)
        _report(units, cap, None)
        if args.list:
            _list_units(units, cap, args.list)
        if args.show:
            _show_full(units, args.show)
        return 0

    file_path = Path(args.file)
    if not file_path.exists():
        parser.error(f"Không tìm thấy {file_path}. Chạy run_llm_chunking.py trước.")

    raw_chunks: list[dict] = json.loads(file_path.read_text(encoding="utf-8"))
    input_ids = _valid_input_ids(raw_chunks)
    units = build_units(raw_chunks, cap=args.cap)

    print(
        f"File: {file_path.name} | {len(raw_chunks)} chunk ({len(input_ids)} hợp lệ) "
        f"-> {len(units)} unit (cap={args.cap})",
        flush=True,
    )
    _report(units, args.cap, input_ids)
    if args.list:
        _list_units(units, args.cap, args.list)
    if args.show:
        _show_full(units, args.show)

    problems = _check_invariant(units, input_ids)
    if problems:
        print(
            f"\n[INVARIANT VỠ] {len(problems)} vi phạm 'mỗi chunk đúng một unit' "
            f"-> KHÔNG ghi {out_path.name} (bước 2 sẽ hỏng im lặng):",
            flush=True,
        )
        for p in problems[:20]:
            print(f"  ! {p}", flush=True)
        return 1

    _write_units(out_path, args.cap, file_path.name, units)
    print(f"\nĐã ghi {len(units)} unit -> {out_path}", flush=True)
    print(
        "VERIFY xong thì chạy BƯỚC 2: python scripts/run_timeline_index.py",
        flush=True,
    )
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
