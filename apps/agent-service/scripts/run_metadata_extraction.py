"""CLI: điền metadata nội dung (times/actors/locations/events) cho từng chunk.

Trích bằng LLM (OpenAI Structured Outputs / json_schema strict, cần OPENAI_API_KEY)
rồi GHI THẲNG (in-place) vào chính `dataset/chunks_llm.json` — không tạo file phụ.
Toàn bộ 4 trường (kể cả times) do LLM trích. Ghi atomic (file tạm rồi thay thế) nên
crash giữa chừng không làm hỏng file nguồn.

Mặc định: 4 luồng song song, xử lý theo LÔ 100 chunk rồi DỪNG chờ Enter (để kiểm
tra), nhấn Enter chạy lô tiếp, Ctrl+C để dừng (đã lưu, lần sau resume tiếp).

Ví dụ:
    # Mặc định: 4 luồng, dừng sau mỗi 100 chunk chờ Enter, ghi vào chunks_llm.json:
    python scripts/run_metadata_extraction.py

    # Chạy thẳng không dừng (vd 8 luồng):
    python scripts/run_metadata_extraction.py --batch-size 0 --workers 8

    # Trích lại từ đầu (bỏ qua marker đã trích):
    python scripts/run_metadata_extraction.py --overwrite

Resume: mỗi chunk trích xong được gắn marker `extracted_prompt_version` trong
metadata; lần chạy sau bỏ qua chunk đã có marker. Chunk lỗi (không marker) sẽ thử lại.
"""

from __future__ import annotations

import argparse
import json
import os
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
from app.indexing.metadata.entity_extractor import PROMPT_VERSION, extract_entities  # noqa: E402
from app.schemas.chunk import Chunk  # noqa: E402

# Mặc định IN-PLACE: đọc và ghi cùng `chunks_llm.json` (gộp metadata vào luôn).
_DEFAULT_FILE = _REPO_ROOT / "dataset" / "chunks_llm.json"


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
    parser.add_argument("--file", default=str(_DEFAULT_FILE), help="File chunks JSON, đọc + ghi in-place.")
    parser.add_argument("--limit", type=int, default=0, help="Chỉ XỬ LÝ N chunk đầu chưa trích (file vẫn giữ đủ chunk). 0 = tất cả.")
    parser.add_argument("--workers", type=int, default=4, help="Số luồng gọi LLM song song.")
    parser.add_argument(
        "--batch-size", type=int, default=100,
        help="Xử lý theo lô N chunk rồi DỪNG chờ Enter để chạy tiếp. 0 = chạy hết không dừng.",
    )
    parser.add_argument("--overwrite", action="store_true", help="Trích lại cả chunk đã có marker.")
    parser.add_argument("--flush-every", type=int, default=50, help="Ghi file sau mỗi N chunk xong.")
    args = parser.parse_args()

    file_path = Path(args.file)
    if not file_path.exists():
        parser.error(f"Không tìm thấy {file_path}. Chạy run_llm_chunking.py trước.")

    # by_id giữ TOÀN BỘ chunk (luôn ghi đủ); --limit chỉ giới hạn số chunk xử lý lần này.
    all_chunks: list[dict] = json.loads(file_path.read_text(encoding="utf-8"))
    by_id = {c["chunk_id"]: c for c in all_chunks}

    # Resume qua marker trong metadata: chunk đã có extracted_prompt_version coi như xong.
    if args.overwrite:
        done: set[str] = set()
    else:
        done = {c["chunk_id"] for c in all_chunks if c["metadata"].get("extracted_prompt_version")}

    todo = [c for c in all_chunks if c["chunk_id"] not in done]
    if args.limit > 0:
        todo = todo[: args.limit]

    settings = get_settings()
    print(
        f"File: {file_path.name} | {len(all_chunks)} chunk "
        f"({len(done)} đã trích, {len(todo)} sẽ xử lý lần này) | "
        f"model={settings.llm_model} | prompt={PROMPT_VERSION} | {args.workers} luồng",
        flush=True,
    )

    def _write() -> None:
        # Ghi atomic: file tạm cùng thư mục rồi os.replace (an toàn cho ghi in-place).
        # GIỮ NGUYÊN thứ tự file (all_chunks là chính các dict đang được sửa tại chỗ).
        # KHÔNG sort theo chunk_index: file gộp nhiều tài liệu thì chunk_index lặp lại
        # theo từng tài liệu, sort toàn cục sẽ XEN KẼ các tài liệu -> segmenter gom run
        # liên tiếp (build_units) sẽ cắt sai ranh giới section.
        tmp = file_path.with_suffix(file_path.suffix + ".tmp")
        tmp.write_text(json.dumps(all_chunks, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, file_path)

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
        md["extracted_prompt_version"] = PROMPT_VERSION  # marker resume + provenance
        return chunk["chunk_id"]

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
            futures = {pool.submit(_process, c): c["chunk_id"] for c in batch}
            for fut in as_completed(futures):
                cid = futures[fut]
                try:
                    fut.result()
                    done.add(cid)
                except Exception as exc:  # noqa: BLE001 - đếm lỗi, không mark done -> resume thử lại
                    errors.append(f"{cid}: {type(exc).__name__}: {exc}")
                    # In NGAY để thấy nguyên nhân kể cả khi Ctrl+C giữa chừng (đừng chờ summary).
                    print(f"    ! {cid}: {type(exc).__name__}: {str(exc)[:160]}", flush=True)
                completed += 1
                if completed % log_every == 0 or completed == total:
                    pct = completed * 100 // total if total else 100
                    print(f"  [{completed:4d}/{total} {pct:3d}%] lỗi={len(errors)}", flush=True)
                if completed % args.flush_every == 0:
                    _write()
        _write()  # chốt file sau mỗi lô

        # Dừng chờ Enter giữa các lô (trừ lô cuối). Chỉ dừng khi stdin là terminal
        # tương tác (tty); nếu là pipe/nền/CI thì chạy tiếp để khỏi treo ở input().
        if args.batch_size > 0 and bi < len(batches) - 1:
            cov = _coverage(list(by_id.values()))
            print(
                f"\n>>> Xong lô {bi + 1}/{len(batches)}: {completed}/{total} chunk "
                f"(actors={cov['with_actors']}, times={cov['with_times']}, lỗi={len(errors)}). "
                f"Đã ghi {file_path}.",
                flush=True,
            )
            if not sys.stdin.isatty():
                print(">>> (stdin không tương tác -> chạy tiếp tự động)", flush=True)
                continue
            try:
                input(">>> Kiểm tra xong, nhấn Enter để chạy lô tiếp (Ctrl+C để dừng)... ")
            except (EOFError, KeyboardInterrupt):
                print("\nDừng theo yêu cầu. Tiến trình đã lưu — lần sau chạy lại sẽ resume tiếp.", flush=True)
                stopped = True
                break

    elapsed = time.perf_counter() - t0
    if stopped:
        print(f"\nĐã dừng giữa chừng tại {completed}/{total} chunk [{elapsed:.1f}s]. Đã ghi -> {file_path}")
        return 0

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
    print(f"Đã ghi -> {file_path}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
