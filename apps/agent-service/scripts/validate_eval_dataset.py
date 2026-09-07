"""Kiểm tính toàn vẹn của retrieval_qa_v2.json — chạy trước mọi lần đo.

Bắt các lỗi làm hỏng số đo mà mắt thường không thấy:

- `sources[].chunk_id` không tồn tại trong `chunks_llm.json`.
- `sources[].text` không khớp trích đoạn của chunk nguồn.
- Loại câu hỏi không thuộc single_query, multi_query, multihop.
- Trùng `id`, JSON hỏng, thiếu field bắt buộc.

Dùng:
    python apps/agent-service/scripts/validate_eval_dataset.py
Exit code 1 nếu có lỗi.
"""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EVAL_DIR = ROOT / "dataset" / "eval"
CHUNKS_PATH = ROOT / "dataset" / "chunks_llm.json"

QUESTION_TYPES = {"single_query", "multi_query", "multihop"}

def normalize(text: str) -> str:
    """Chuẩn hoá Unicode và khoảng trắng để so khớp trích đoạn nguồn."""
    return " ".join(unicodedata.normalize("NFC", text).split())

def load_json(path: Path) -> list[dict]:
    """Đọc file nhãn — JSON mảng in dọc."""
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"[{path.name}] Không đọc được JSON: {exc}") from exc
    if not isinstance(rows, list) or not rows or any(not isinstance(r, dict) for r in rows):
        raise SystemExit(f"[{path.name}] Phải là mảng JSON không rỗng gồm các object.")
    return rows

def validate_rows(rows: list[dict], chunks: dict[str, dict]) -> list[str]:
    """Kiểm tra cấu trúc và nguồn; không chấm ngữ nghĩa đáp án hay nhãn multihop."""
    errors: list[str] = []
    seen_ids: set[str] = set()
    for index, row in enumerate(rows, start=1):
        tag = f"[dòng {index}: {row.get('id', '?')}]"
        for field in ("id", "question", "type", "gold_answer"):
            value = row.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{tag} `{field}` phải là chuỗi không rỗng")
        item_id = row.get("id")
        if isinstance(item_id, str):
            if item_id in seen_ids:
                errors.append(f"{tag} id bị trùng")
            seen_ids.add(item_id)
        kind = row.get("type")
        if not isinstance(kind, str) or kind not in QUESTION_TYPES:
            errors.append(f"{tag} type phải là single_query, multi_query hoặc multihop")
        sources = row.get("sources")
        if not isinstance(sources, list) or not sources:
            errors.append(f"{tag} `sources` phải là danh sách không rỗng")
            continue
        for number, source in enumerate(sources, start=1):
            source_tag = f"{tag} sources[{number}]"
            if not isinstance(source, dict):
                errors.append(f"{source_tag} phải là object chứa chunk_id và text")
                continue
            cid, text = source.get("chunk_id"), source.get("text")
            if not isinstance(cid, str) or cid not in chunks:
                errors.append(f"{source_tag} chunk_id không tồn tại: {cid}")
            if not isinstance(text, str) or not text.strip():
                errors.append(f"{source_tag} text phải là chuỗi không rỗng")
            elif isinstance(cid, str) and cid in chunks:
                if normalize(text) not in normalize(chunks[cid]["text"]):
                    errors.append(f"{source_tag} text không khớp trích đoạn trong chunk {cid}")
    return errors

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dataset", default="retrieval_qa_v2.json", help="tên file v2 trong dataset/eval/")
    args = ap.parse_args()
    rows = load_json(EVAL_DIR / args.dataset)
    chunks = {c["chunk_id"]: c for c in load_json(CHUNKS_PATH)}
    errors = validate_rows(rows, chunks)
    for error in errors:
        print(f"LỖI {error}")
    print(f"{args.dataset}: {len(rows)} câu, {len(errors)} lỗi.")
    return 1 if errors else 0

if __name__ == "__main__":
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main())
