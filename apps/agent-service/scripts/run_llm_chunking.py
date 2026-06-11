"""CLI: chạy pipeline chunking trên `lichsu.clean.md` -> `dataset/chunks_llm.json`.

Ví dụ:
    # Chạy đầy đủ (cần OPENAI_API_KEY cho Level 4)
    python scripts/run_llm_chunking.py

    # Dry-run 50k ký tự đầu, không gọi LLM (không ghi file)
    python scripts/run_llm_chunking.py --limit 50000 --no-llm

Lưu ý: input phải là file ĐÃ preprocess. Nếu chưa có lichsu.clean.md, chạy trước:
    python scripts/preprocess_dataset.py --input ../../lichsu.md --output ../../lichsu.clean.md
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_APP_ROOT = _THIS_DIR.parent  # apps/agent-service
_REPO_ROOT = _THIS_DIR.parents[2]  # gốc repo
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))

from app.indexing.llm_chunker import chunk_document  # noqa: E402
from app.schemas.chunk import Chunk  # noqa: E402

_DEFAULT_INPUT = _REPO_ROOT / "lichsu.clean.md"
_DEFAULT_OUTPUT = _REPO_ROOT / "dataset" / "chunks_llm.json"


def _token_summary(chunks: list[dict]) -> dict[str, object]:
    counts = [c["metadata"]["text_token_count"] for c in chunks]
    if not counts:
        return {"count": 0}
    return {
        "count": len(counts),
        "min": min(counts),
        "max": max(counts),
        "avg": round(sum(counts) / len(counts), 1),
        "over_700": sum(1 for c in counts if c > 700),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=str(_DEFAULT_INPUT), help="File đã preprocess (lichsu.clean.md).")
    parser.add_argument("--output", default=str(_DEFAULT_OUTPUT), help="File JSON đầu ra.")
    parser.add_argument(
        "--limit", type=int, default=0, help="Chỉ xử lý N ký tự đầu (dry-run, không ghi). 0 = toàn bộ."
    )
    parser.add_argument("--no-llm", action="store_true", help="Tắt Level 4 (LLM), chỉ dùng fallback Chonkie.")
    parser.add_argument("--document-title", default="lichsu.md", help="Tên tài liệu hiển thị trong embedding_text.")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        parser.error(
            f"Không tìm thấy {input_path}.\n"
            "Hãy chạy preprocess trước:\n"
            "  python scripts/preprocess_dataset.py --input ../../lichsu.md --output ../../lichsu.clean.md"
        )

    text = input_path.read_text(encoding="utf-8")
    if args.limit > 0:
        text = text[: args.limit]

    print(f"Input: {input_path} ({len(text):,} ký tự){' [dry-run, limit]' if args.limit else ''}", flush=True)
    t0 = time.perf_counter()
    chunks, stats = chunk_document(
        text,
        use_llm=not args.no_llm,
        document_title=args.document_title,
        source_file=input_path.name,
        verbose=True,
    )
    elapsed = time.perf_counter() - t0

    # Validate toàn bộ chunk theo schema trước khi ghi.
    errors: list[str] = []
    for chunk in chunks:
        try:
            Chunk.model_validate(chunk)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{chunk.get('chunk_id')}: {exc}")

    print(f"Stats: {json.dumps(stats.as_dict(), ensure_ascii=False)} [{elapsed:.1f}s]")
    print("Token:", json.dumps(_token_summary(chunks), ensure_ascii=False))
    if errors:
        print(f"[CẢNH BÁO] {len(errors)} chunk lỗi schema:")
        for err in errors[:10]:
            print("  -", err)

    if args.limit > 0:
        print("\n--- preview 3 chunk đầu ---")
        for chunk in chunks[:3]:
            md = chunk["metadata"]
            print(f"\n[{chunk['chunk_id']}] headings={md['headings']} "
                  f"lines={md['start_line']}-{md['end_line']} tokens={md['text_token_count']}")
            preview = chunk["text"][:200].replace("\n", " ")
            print("  ", preview, "..." if len(chunk["text"]) > 200 else "")
        return 0

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nĐã ghi {len(chunks)} chunk -> {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
