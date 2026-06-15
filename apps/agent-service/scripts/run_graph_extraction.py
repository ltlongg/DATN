"""CLI: trích entity + quan hệ cho từng chunk -> `dataset/graph_extractions.json`.

Tách RIÊNG bước trích graph khỏi pipeline index (run_graph_index.py) để "vừa làm vừa
check": trích bằng LLM (OpenAI Structured Outputs, cần OPENAI_API_KEY), GHI THẲNG vào
sổ cache `dataset/graph_extractions.json` — chính là artifact mà run_graph_index.py đọc
để merge Neo4j. Trích xong KHÔNG đụng Neo4j; merge chạy sau bằng:
    python scripts/run_graph_index.py --remerge --skip-vectors

Mặc định: 4 luồng song song, xử lý theo LÔ 100 chunk rồi DỪNG chờ Enter (để kiểm tra
graph_extractions.json), nhấn Enter chạy lô tiếp, Ctrl+C để dừng (đã lưu, resume tiếp).

Ví dụ:
    # Mặc định: 4 luồng, dừng sau mỗi 100 chunk chờ Enter:
    python scripts/run_graph_extraction.py

    # Chạy thẳng không dừng (vd 8 luồng):
    python scripts/run_graph_extraction.py --batch-size 0 --workers 8

    # Trích lại từ đầu (bỏ qua cache cũ):
    python scripts/run_graph_extraction.py --overwrite

Resume: mỗi chunk trích xong lưu vào cache với `prompt_version`; lần chạy sau bỏ qua
chunk đã có prompt_version khớp. Chunk lỗi (không vào cache) sẽ thử lại lần sau.
"""

from __future__ import annotations

import argparse
import json
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

_THIS_DIR = Path(__file__).resolve().parent
_APP_ROOT = _THIS_DIR.parent  # apps/agent-service
_REPO_ROOT = _THIS_DIR.parents[2]  # gốc repo
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))

from app.core.config import get_settings  # noqa: E402
from app.core.llm import get_openai_client  # noqa: E402
from app.indexing.graph.entity_relation_extractor import (  # noqa: E402
    GRAPH_PROMPT_VERSION,
    extract_graph,
)
from app.tools.graph_rag.chunks import prepare_chunk_records  # noqa: E402

_DEFAULT_FILE = _REPO_ROOT / "dataset" / "chunks_llm.json"
_ARTIFACT = _REPO_ROOT / "dataset" / "graph_extractions.json"


def _load_artifact(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return {}  # file rỗng (vd xóa để chạy lại) -> coi như cache trống
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}  # cache hỏng/ghi dở -> bỏ qua, trích lại từ đầu
    return data if isinstance(data, dict) else {}


def _write_artifact(path: Path, cache: dict[str, Any]) -> None:
    # Ghi atomic: file tạm cùng thư mục rồi os.replace (crash giữa chừng không hỏng cache).
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _summary(cache: dict[str, Any]) -> dict[str, int]:
    n_ent = sum(len(v.get("entities", [])) for v in cache.values())
    n_rel = sum(len(v.get("relations", [])) for v in cache.values())
    return {"chunks": len(cache), "entities": n_ent, "relations": n_rel}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", default=str(_DEFAULT_FILE), help="File chunks JSON nguồn.")
    parser.add_argument("--artifact", default=str(_ARTIFACT), help="Sổ cache graph (đọc + ghi).")
    parser.add_argument("--limit", type=int, default=0, help="Chỉ XỬ LÝ N chunk đầu chưa trích. 0 = tất cả.")
    parser.add_argument("--workers", type=int, default=4, help="Số luồng gọi LLM song song.")
    parser.add_argument(
        "--batch-size", type=int, default=100,
        help="Xử lý theo lô N chunk rồi DỪNG chờ Enter để chạy tiếp. 0 = chạy hết không dừng.",
    )
    parser.add_argument("--overwrite", action="store_true", help="Trích lại cả chunk đã có trong cache.")
    parser.add_argument("--flush-every", type=int, default=50, help="Ghi cache sau mỗi N chunk xong.")
    args = parser.parse_args()

    file_path = Path(args.file)
    if not file_path.exists():
        parser.error(f"Không tìm thấy {file_path}. Chạy run_llm_chunking.py trước.")
    artifact_path = Path(args.artifact)

    raw_chunks: list[dict] = json.loads(file_path.read_text(encoding="utf-8"))
    records = prepare_chunk_records(raw_chunks)
    cache = _load_artifact(artifact_path)

    # Resume qua cache: chunk có prompt_version khớp coi như xong (trừ --overwrite).
    if args.overwrite:
        done: set[str] = set()
    else:
        done = {
            cid for cid, v in cache.items()
            if v.get("prompt_version") == GRAPH_PROMPT_VERSION
        }

    todo = [r for r in records if r["chunk_id"] not in done]
    if args.limit > 0:
        todo = todo[: args.limit]

    settings = get_settings()
    model = settings.graph_llm_model or settings.llm_model
    print(
        f"File: {file_path.name} | {len(records)} chunk "
        f"({len(done)} đã trích, {len(todo)} sẽ xử lý lần này) | "
        f"model={model} | prompt={GRAPH_PROMPT_VERSION} | {args.workers} luồng",
        flush=True,
    )

    client = get_openai_client()
    errors: list[str] = []
    t0 = time.perf_counter()

    def _process(record: dict) -> str:
        result = extract_graph(
            record["text"],
            record["metadata"].get("headings"),
            client=client,
            model=model,
            chunk_id=record["chunk_id"],
        )
        cache[record["chunk_id"]] = {
            "prompt_version": GRAPH_PROMPT_VERSION,
            "entities": [e.model_dump() for e in result.entities],
            "relations": [rel.model_dump() for rel in result.relations],
        }
        return record["chunk_id"]

    def _batches(items: list[dict], size: int) -> list[list[dict]]:
        if size <= 0:
            return [items]
        return [items[i : i + size] for i in range(0, len(items), size)]

    total = len(todo)
    completed = 0
    log_every = max(1, total // 20)
    batches = _batches(todo, args.batch_size)
    stopped = False
    for bi, batch in enumerate(batches):
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(_process, r): r["chunk_id"] for r in batch}
            for fut in as_completed(futures):
                cid = futures[fut]
                try:
                    fut.result()
                except Exception as exc:  # noqa: BLE001 - đếm lỗi, không vào cache -> resume thử lại
                    errors.append(f"{cid}: {type(exc).__name__}: {exc}")
                    # In rộng hơn (500 ký tự) để thấy input_value LLM bịa ở ValidationError
                    # — vd entities.N.type = 'Lãnh đạo' (ngoài 7 loại). Pydantic in input_value
                    # SAU danh sách loại hợp lệ nên 160 ký tự cũ cắt mất.
                    msg = " ".join(str(exc).split())
                    print(f"    ! {cid}: {type(exc).__name__}: {msg[:500]}", flush=True)
                completed += 1
                if completed % log_every == 0 or completed == total:
                    pct = completed * 100 // total if total else 100
                    print(f"  [{completed:4d}/{total} {pct:3d}%] lỗi={len(errors)}", flush=True)
                if completed % args.flush_every == 0:
                    _write_artifact(artifact_path, cache)
        _write_artifact(artifact_path, cache)  # chốt cache sau mỗi lô

        # Dừng chờ Enter giữa các lô (trừ lô cuối). Chỉ dừng khi stdin là tty tương tác;
        # pipe/nền/CI thì chạy tiếp để khỏi treo ở input().
        if args.batch_size > 0 and bi < len(batches) - 1:
            s = _summary(cache)
            print(
                f"\n>>> Xong lô {bi + 1}/{len(batches)}: {completed}/{total} chunk "
                f"(cache: {s['entities']} entity, {s['relations']} relation, lỗi={len(errors)}). "
                f"Đã ghi {artifact_path}.",
                flush=True,
            )
            if not sys.stdin.isatty():
                print(">>> (stdin không tương tác -> chạy tiếp tự động)", flush=True)
                continue
            try:
                input(">>> Kiểm tra xong, nhấn Enter để chạy lô tiếp (Ctrl+C để dừng)... ")
            except (EOFError, KeyboardInterrupt):
                print("\nDừng theo yêu cầu. Cache đã lưu — lần sau chạy lại sẽ resume tiếp.", flush=True)
                stopped = True
                break

    elapsed = time.perf_counter() - t0
    if stopped:
        print(f"\nĐã dừng giữa chừng tại {completed}/{total} chunk [{elapsed:.1f}s]. Cache -> {artifact_path}")
        return 0

    print(f"\nXong trong {elapsed:.1f}s.", json.dumps(_summary(cache), ensure_ascii=False))
    if errors:
        print(f"[LỖI] {len(errors)} chunk thất bại (sẽ thử lại lần chạy sau):")
        for e in errors[:10]:
            print("  -", e)
    print(f"Cache -> {artifact_path}")
    print("Merge vào Neo4j: python scripts/run_graph_index.py --remerge --skip-vectors")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
