"""CLI: điền metadata nội dung (times/actors/locations/events) cho từng chunk.

Đọc `dataset/chunks_llm.json` (đã có metadata nền) -> điền 4 trường nội dung bằng
LLM (OpenAI Structured Outputs / json_schema strict, cần OPENAI_API_KEY) -> ghi
`dataset/chunks_meta.json` (non-destructive). Toàn bộ 4 trường (kể cả times) do LLM trích.

Ví dụ:
    # Thử 20 chunk đầu:
    python scripts/run_metadata_extraction.py --limit 20

    # Chạy đầy đủ (1213 chunk), 8 luồng, có resume:
    python scripts/run_metadata_extraction.py

    # Chạy lại từ đầu, bỏ qua tiến trình cũ:
    python scripts/run_metadata_extraction.py --overwrite

Resume: chỉ chunk trích thành công mới được ghi vào file tiến trình
`<output>.progress.json`; lần chạy sau bỏ qua các chunk này. Chunk lỗi sẽ được thử lại.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_APP_ROOT = _THIS_DIR.parent  # apps/agent-service
_REPO_ROOT = _THIS_DIR.parents[2]  # gốc repo
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))

from app.core.config import get_settings  # noqa: E402
from app.core.llm import get_openai_client  # noqa: E402
from app.indexing.metadata.entity_extractor import extract_entities  # noqa: E402
from app.schemas.chunk import Chunk  # noqa: E402

_DEFAULT_INPUT = _REPO_ROOT / "dataset" / "chunks_llm.json"
_DEFAULT_OUTPUT = _REPO_ROOT / "dataset" / "chunks_meta.json"


def _progress_path(output: Path) -> Path:
    return output.with_suffix(".progress.json")


def _load_done(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        return set(json.loads(path.read_text(encoding="utf-8")))
    except Exception:  # noqa: BLE001 - file hỏng thì coi như chưa có tiến trình
        return set()


def _coverage(chunks: list[dict]) -> dict[str, object]:
    n = len(chunks) or 1
    def _has(field: str) -> int:
        return sum(1 for c in chunks if c["metadata"].get(field))
    return {
        "chunks": len(chunks),
        "with_times": _has("times"),
        "with_actors": _has("actors"),
        "with_locations": _has("locations"),
        "with_events": _has("events"),
        "pct_actors": round(_has("actors") * 100 / n, 1),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=str(_DEFAULT_INPUT), help="chunks_llm.json (đã chunk).")
    parser.add_argument("--output", default=str(_DEFAULT_OUTPUT), help="File JSON đầu ra.")
    parser.add_argument("--limit", type=int, default=0, help="Chỉ xử lý N chunk đầu. 0 = tất cả.")
    parser.add_argument("--workers", type=int, default=8, help="Số luồng gọi LLM song song.")
    parser.add_argument("--overwrite", action="store_true", help="Bỏ qua tiến trình cũ, trích lại từ đầu.")
    parser.add_argument("--flush-every", type=int, default=50, help="Ghi output + progress sau mỗi N chunk xong.")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        parser.error(f"Không tìm thấy {input_path}. Chạy run_llm_chunking.py trước.")

    output_path = Path(args.output)
    progress_path = _progress_path(output_path)

    chunks: list[dict] = json.loads(input_path.read_text(encoding="utf-8"))
    if args.limit > 0:
        chunks = chunks[: args.limit]
    by_id = {c["chunk_id"]: c for c in chunks}

    # Resume: nạp output cũ (giữ dữ liệu đã trích) + tập chunk đã xong.
    done: set[str] = set()
    if not args.overwrite and output_path.exists():
        try:
            prev = {c["chunk_id"]: c for c in json.loads(output_path.read_text(encoding="utf-8"))}
            for cid, prev_chunk in prev.items():
                if cid in by_id:
                    by_id[cid]["metadata"].update(
                        {k: prev_chunk["metadata"].get(k, []) for k in ("times", "actors", "locations", "events")}
                    )
            done = _load_done(progress_path) & set(by_id)
        except Exception as exc:  # noqa: BLE001
            print(f"[CẢNH BÁO] Không đọc được output cũ ({exc}); chạy lại từ đầu.", flush=True)

    todo = [c for c in chunks if c["chunk_id"] not in done]
    settings = get_settings()
    print(
        f"Input: {input_path.name} | {len(chunks)} chunk "
        f"({len(done)} đã xong, {len(todo)} cần xử lý) | "
        f"model={settings.llm_model} | {args.workers} luồng",
        flush=True,
    )

    def _write() -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        ordered = sorted(by_id.values(), key=lambda c: c["metadata"]["chunk_index"])
        output_path.write_text(json.dumps(ordered, ensure_ascii=False, indent=2), encoding="utf-8")
        progress_path.write_text(json.dumps(sorted(done), ensure_ascii=False), encoding="utf-8")

    client = get_openai_client()
    errors: list[str] = []
    t0 = time.perf_counter()

    def _process(chunk: dict) -> str:
        md = chunk["metadata"]
        ents = extract_entities(
            chunk["text"], md.get("headings"), client=client, model=settings.llm_model
        )
        md["times"] = ents.times
        md["actors"] = ents.actors
        md["locations"] = ents.locations
        md["events"] = ents.events
        return chunk["chunk_id"]

    completed = 0
    log_every = max(1, len(todo) // 20)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(_process, c): c["chunk_id"] for c in todo}
        for fut in as_completed(futures):
            cid = futures[fut]
            try:
                fut.result()
                done.add(cid)
            except Exception as exc:  # noqa: BLE001 - đếm lỗi, không mark done -> resume thử lại
                errors.append(f"{cid}: {type(exc).__name__}: {exc}")
            completed += 1
            if completed % log_every == 0 or completed == len(todo):
                pct = completed * 100 // len(todo) if todo else 100
                print(f"  [{completed:4d}/{len(todo)} {pct:3d}%] lỗi={len(errors)}", flush=True)
            if completed % args.flush_every == 0:
                _write()

    _write()
    elapsed = time.perf_counter() - t0

    # Validate schema toàn bộ.
    schema_errors = 0
    for c in by_id.values():
        try:
            Chunk.model_validate(c)
        except Exception:  # noqa: BLE001
            schema_errors += 1

    print(f"\nXong trong {elapsed:.1f}s. Coverage:", json.dumps(_coverage(list(by_id.values())), ensure_ascii=False))
    if errors:
        print(f"[LỖI] {len(errors)} chunk thất bại (sẽ thử lại lần chạy sau):")
        for e in errors[:10]:
            print("  -", e)
    if schema_errors:
        print(f"[CẢNH BÁO] {schema_errors} chunk lỗi schema.")
    print(f"Đã ghi -> {output_path}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
