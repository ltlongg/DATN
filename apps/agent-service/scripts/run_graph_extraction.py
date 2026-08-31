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
chunk đã có prompt_version khớp. Mỗi kết quả LLM được fsync ngay vào journal trước khi
worker báo hoàn tất, nên kill process/mất điện trước lần flush artifact kế tiếp vẫn resume
được. Chunk lỗi (không vào cache) sẽ thử lại lần sau.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Cấu hình logging để warning "Bỏ ... relation mồ côi" (từ entity_relation_extractor)
# hiện rõ ràng kèm timestamp/level, nhất quán với run_graph_index.py.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

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
_IO_RETRIES = 5


class _CheckpointWriteError(RuntimeError):
    """Kết quả LLM đã có nhưng không thể ghi checkpoint bền vững."""

    def __init__(self, chunk_id: str, entry: dict[str, Any], cause: OSError) -> None:
        super().__init__(f"Không thể checkpoint {chunk_id}: {cause}")
        self.chunk_id = chunk_id
        self.entry = entry


def _load_artifact(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return {}  # file rỗng (vd xóa để chạy lại) -> coi như cache trống
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        # Không âm thầm coi cache hỏng là rỗng: việc đó gọi lại toàn bộ LLM và tốn tiền.
        raise RuntimeError(
            f"Cache {path} không phải JSON hợp lệ; giữ nguyên file để phục hồi thủ công "
            "thay vì trích lại từ đầu."
        ) from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"Cache {path} phải là JSON object, nhận {type(data).__name__}.")
    return data


def _journal_path(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".journal.jsonl")


def _replace_with_retry(source: Path, destination: Path) -> None:
    """Retry lỗi khóa file tạm thời (thường gặp trên Windows/antivirus)."""
    for attempt in range(_IO_RETRIES):
        try:
            os.replace(source, destination)
            return
        except OSError:
            if attempt == _IO_RETRIES - 1:
                raise
            time.sleep(0.05 * (2**attempt))


def _write_artifact(path: Path, cache: dict[str, Any]) -> None:
    # Chỉ main thread gọi hàm này. Ghi + fsync file tạm rồi replace nguyên tử để crash
    # không làm hỏng artifact cũ; retry replace vì Windows đôi lúc khóa file thoáng qua.
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    payload = json.dumps(cache, ensure_ascii=False, indent=2)
    with tmp.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    _replace_with_retry(tmp, path)


def _append_journal(
    path: Path,
    chunk_id: str,
    entry: dict[str, Any],
    lock: threading.Lock,
) -> None:
    """Append + fsync một kết quả trước khi worker trả về.

    Lock giữ mỗi JSON record trên đúng một dòng. Artifact chính vẫn chỉ do main thread
    cập nhật, nên không còn race `dictionary changed size during iteration`.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(
        {"chunk_id": chunk_id, "entry": entry},
        ensure_ascii=False,
        separators=(",", ":"),
    ) + "\n"
    last_error: OSError | None = None
    for attempt in range(_IO_RETRIES):
        try:
            with lock, path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(line)
                stream.flush()
                os.fsync(stream.fileno())
            return
        except OSError as exc:
            last_error = exc
            if attempt < _IO_RETRIES - 1:
                time.sleep(0.05 * (2**attempt))
    assert last_error is not None
    raise _CheckpointWriteError(chunk_id, entry, last_error)


def _replay_journal(path: Path, cache: dict[str, Any]) -> int:
    """Khôi phục các record journal nguyên vẹn; bỏ qua dòng cuối bị torn write."""
    if not path.exists():
        return 0
    recovered = 0
    # errors=replace để một code point UTF-8 bị cắt ở cuối file không chặn phục hồi
    # toàn bộ các dòng nguyên vẹn phía trước.
    with path.open("r", encoding="utf-8", errors="replace") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                chunk_id = record["chunk_id"]
                entry = record["entry"]
                if not isinstance(chunk_id, str) or not isinstance(entry, dict):
                    raise ValueError("record không đúng schema")
            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                logging.warning(
                    "Bỏ journal record hỏng %s:%d (%s)", path, line_number, exc
                )
                continue
            cache[chunk_id] = entry
            recovered += 1
    return recovered


def _clear_journal(path: Path) -> None:
    """Xóa journal sau khi artifact đã replace thành công; lỗi xóa là vô hại."""
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        # Lần chạy sau replay trùng theo chunk_id nên vẫn idempotent.
        logging.warning("Không xóa được journal %s: %s", path, exc)


def _compact_checkpoint(
    artifact_path: Path,
    journal_path: Path,
    cache: dict[str, Any],
) -> None:
    # Thứ tự này là invariant phục hồi: artifact bền vững trước, rồi mới xóa journal.
    _write_artifact(artifact_path, cache)
    _clear_journal(journal_path)


def _recover_checkpoint(
    artifact_path: Path,
    journal_path: Path,
    cache: dict[str, Any],
) -> int:
    """Replay và compact journal cũ, kể cả khi journal chỉ có torn record."""
    if not journal_path.exists():
        return 0
    recovered = _replay_journal(journal_path, cache)
    # Luôn clear qua compact: nếu journal chỉ có dòng bị cắt, append tiếp vào đó sẽ
    # làm hỏng cả record hợp lệ đầu tiên của lần chạy mới.
    _compact_checkpoint(artifact_path, journal_path, cache)
    return recovered


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

    if args.workers <= 0:
        parser.error("--workers phải lớn hơn 0.")
    if args.flush_every <= 0:
        parser.error("--flush-every phải lớn hơn 0.")

    file_path = Path(args.file)
    if not file_path.exists():
        parser.error(f"Không tìm thấy {file_path}. Chạy run_llm_chunking.py trước.")
    artifact_path = Path(args.artifact)

    raw_chunks: list[dict] = json.loads(file_path.read_text(encoding="utf-8"))
    records = prepare_chunk_records(raw_chunks)
    cache = _load_artifact(artifact_path)
    journal_path = _journal_path(artifact_path)
    recovered = _recover_checkpoint(artifact_path, journal_path, cache)
    if recovered:
        print(f"[resume] Khôi phục {recovered} kết quả từ {journal_path.name}.", flush=True)

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
    journal_lock = threading.Lock()

    def _process(record: dict) -> tuple[str, dict[str, Any]]:
        result = extract_graph(
            record["text"],
            client=client,
            model=model,
            chunk_id=record["chunk_id"],
        )
        entry = {
            "prompt_version": GRAPH_PROMPT_VERSION,
            "entities": [e.model_dump() for e in result.entities],
            "relations": [rel.model_dump() for rel in result.relations],
        }
        # Durable trước khi báo future hoàn tất. Worker tuyệt đối không sửa `cache`.
        _append_journal(journal_path, record["chunk_id"], entry, journal_lock)
        return record["chunk_id"], entry

    def _batches(items: list[dict], size: int) -> list[list[dict]]:
        if size <= 0:
            return [items]
        return [items[i : i + size] for i in range(0, len(items), size)]

    total = len(todo)
    completed = 0
    log_every = max(1, total // 20)
    batches = _batches(todo, args.batch_size)
    stopped = False
    try:
        for bi, batch in enumerate(batches):
            with ThreadPoolExecutor(max_workers=args.workers) as pool:
                futures = {pool.submit(_process, r): r["chunk_id"] for r in batch}
                for fut in as_completed(futures):
                    cid = futures[fut]
                    try:
                        saved_cid, entry = fut.result()
                        cache[saved_cid] = entry  # chỉ main thread sửa cache
                    except _CheckpointWriteError as exc:
                        # Giữ kết quả trong RAM để lần chốt khẩn cấp còn một cơ hội lưu,
                        # rồi dừng ngay thay vì tiếp tục đốt tiền khi storage đang lỗi.
                        cache[exc.chunk_id] = exc.entry
                        raise
                    except Exception as exc:  # noqa: BLE001 - lỗi LLM -> resume thử lại
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
            _compact_checkpoint(artifact_path, journal_path, cache)  # chốt sau mỗi lô

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
    except KeyboardInterrupt:
        # Khi rời ThreadPoolExecutor, các request đang chạy đã kết thúc và fsync journal.
        _replay_journal(journal_path, cache)
        _compact_checkpoint(artifact_path, journal_path, cache)
        elapsed = time.perf_counter() - t0
        print(
            f"\nĐã nhận Ctrl+C và chốt checkpoint tại {len(cache)} chunk "
            f"[{elapsed:.1f}s]. Cache -> {artifact_path}",
            flush=True,
        )
        return 130
    except BaseException:
        # Không nuốt lỗi lập trình/hệ thống, nhưng cứu mọi record worker đã fsync trước.
        try:
            _replay_journal(journal_path, cache)
            _compact_checkpoint(artifact_path, journal_path, cache)
        except Exception as save_exc:  # noqa: BLE001 - giữ nguyên exception gốc
            logging.error(
                "Chốt artifact khẩn cấp thất bại (%s). Journal vẫn ở %s",
                save_exc,
                journal_path,
            )
        raise

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
