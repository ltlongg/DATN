"""CLI: chạy pipeline chunking trên `lichsu.clean.md` -> `dataset/chunks_llm.json`.

MỌI tài liệu dùng CHUNG một file chunks: chạy lại với `--input` khác sẽ GỘP vào file
sẵn có chứ không ghi đè — chỉ nhóm chunk cùng `source_file` bị thay bằng bản mới
(idempotent khi chunk lại cùng một tài liệu). `chunk_id` đã có tiền tố theo
`source_file` (xem `llm_chunker._chunk_id_prefix`) nên id không đụng nhau.

Ví dụ:
    # Chạy đầy đủ (cần OPENAI_API_KEY cho Level 4)
    python scripts/run_llm_chunking.py

    # Thêm tài liệu thứ hai vào cùng dataset/chunks_llm.json
    python scripts/run_llm_chunking.py --input ../../tap1.clean.md

    # Dry-run 50k ký tự đầu, không gọi LLM (không ghi file)
    python scripts/run_llm_chunking.py --limit 50000 --no-llm

Lưu ý: input phải là file ĐÃ preprocess. Nếu chưa có lichsu.clean.md, chạy trước:
    python scripts/preprocess_dataset.py --input ../../lichsu.md --output ../../lichsu.clean.md
"""

from __future__ import annotations

import argparse
import json
import os
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

def _source_file(chunk: dict) -> str | None:
    md = chunk.get("metadata")
    return md.get("source_file") if isinstance(md, dict) else None

def _load_existing(path: Path) -> list[dict]:
    """Đọc file chunks sẵn có để gộp. Chưa có -> []. HỎNG -> nổ, KHÔNG trả [].

    Nuốt lỗi ở đây đồng nghĩa ghi đè trắng cả kho chunk của các tài liệu khác
    (mỗi chunk tốn tiền LLM) — thà dừng để người chạy xử lý file hỏng.
    """
    if not path.exists():
        return []
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return []
    data = json.loads(raw)  # JSONDecodeError -> dừng hẳn, cố ý
    if not isinstance(data, list):
        raise ValueError(f"{path} không phải JSON list.")
    return data

def _merge_chunks(existing: list[dict], new: list[dict], source_file: str) -> tuple[list[dict], int]:
    """Thay trọn nhóm chunk cùng `source_file` bằng bản mới, giữ nguyên tài liệu khác.

    Chunk mỗi tài liệu phải nằm LIỀN KHỐI theo thứ tự văn bản: segmenter (`build_units`)
    gom run liên tiếp, xen kẽ tài liệu sẽ phá ranh giới section. Nên bản mới được chèn
    ĐÚNG vị trí khối cũ (tài liệu đã có) hoặc nối vào cuối (tài liệu mới).

    Trả (danh sách đã gộp, số chunk cũ bị thay).
    """
    kept = [c for c in existing if _source_file(c) != source_file]
    replaced = len(existing) - len(kept)

    collision = {c["chunk_id"] for c in kept} & {c["chunk_id"] for c in new}
    if collision:
        raise ValueError(
            f"{len(collision)} chunk_id đụng tài liệu khác trong file, "
            f"ví dụ {sorted(collision)[:3]}. Kiểm tra _chunk_id_prefix/source_file."
        )

    if replaced == 0:
        return kept + new, 0
    # Số chunk của tài liệu KHÁC đứng trước khối cũ = vị trí chèn trong `kept`.
    first = next(i for i, c in enumerate(existing) if _source_file(c) == source_file)
    at = sum(1 for c in existing[:first] if _source_file(c) != source_file)
    return kept[:at] + new + kept[at:], replaced

def _by_document(chunks: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for c in chunks:
        counts[_source_file(c) or "(không rõ)"] = counts.get(_source_file(c) or "(không rõ)", 0) + 1
    return counts

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
    parser.add_argument(
        "--fresh", action="store_true",
        help="Ghi đè TRỌN file output (xoá chunk của mọi tài liệu khác). Mặc định là gộp.",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        parser.error(
            f"Không tìm thấy {input_path}.\n"
            "Hãy chạy preprocess trước:\n"
            "  python scripts/preprocess_dataset.py --input ../../lichsu.md --output ../../lichsu.clean.md"
        )

    source_file = input_path.name  # khóa nhóm chunk theo tài liệu trong file gộp
    text = input_path.read_text(encoding="utf-8")
    if args.limit > 0:
        text = text[: args.limit]

    print(f"Input: {input_path} ({len(text):,} ký tự){' [dry-run, limit]' if args.limit else ''}", flush=True)
    t0 = time.perf_counter()
    chunks, stats = chunk_document(
        text,
        use_llm=not args.no_llm,
        document_title=args.document_title,
        source_file=source_file,
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
    if args.fresh:
        merged, replaced = chunks, len(_load_existing(output_path))
        if replaced:
            print(f"[--fresh] Ghi đè trọn file: {replaced} chunk cũ (mọi tài liệu) bị xoá.")
    else:
        merged, replaced = _merge_chunks(_load_existing(output_path), chunks, source_file)

    # Ghi atomic: file tạm cùng thư mục rồi replace. Crash giữa chừng không để lại
    # file chunks cụt — mất nó là phải chunk lại bằng LLM cho MỌI tài liệu trong đó.
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = output_path.with_suffix(output_path.suffix + ".tmp")
    tmp.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, output_path)

    action = f"thay {replaced} chunk cũ của {source_file}" if replaced else f"thêm mới {source_file}"
    print(f"\nĐã ghi {len(merged)} chunk -> {output_path} ({action}, +{len(chunks)} chunk).")
    print("Theo tài liệu:", json.dumps(_by_document(merged), ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
