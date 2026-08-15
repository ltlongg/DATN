"""Kiểm tính toàn vẹn của bộ eval trong `dataset/eval/` — chạy TRƯỚC mọi lần đo.

Bắt các lỗi làm hỏng số đo mà mắt thường không thấy:

- `gold_chunk_ids` / `supporting_chunk_ids` trỏ tới chunk không tồn tại trong
  `chunks_llm.json` (chunk_id gõ sai, hoặc corpus đã reindex đổi id) -> Recall tính ra
  luôn thấp mà không ai biết vì sao.
- `key_facts` không xuất hiện nguyên văn trong text của chunk gold -> chấm fact coverage
  sẽ phạt oan hệ thống.
- Sai luật nhãn: `expected_step_count=2` mà thiếu `hop1/hop2`, hoặc câu multi-hop khai
  `single_chunk_contains_both=false` nhưng thực tế có chunk chứa cả hai mắt xích.
- Trùng `id`, JSON hỏng, thiếu field bắt buộc.

Dùng:
    python apps/agent-service/scripts/validate_eval_dataset.py
Exit code 1 nếu có lỗi.
"""

from __future__ import annotations

import json
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EVAL_DIR = ROOT / "dataset" / "eval"
CHUNKS_PATH = ROOT / "dataset" / "chunks_llm.json"

REQUIRED_FIELDS = {
    "retrieval_qa.json": ["id", "question", "type", "gold_chunk_ids", "key_facts", "gold_answer", "expected_mode", "expected_step_count"],
    "plan_routing.json": ["id", "question", "history", "expected_route", "expected_mode", "expected_step_count"],
    "guardrails.json": ["id", "question", "expected_action", "expected_categories"],
    "negative.json": ["id", "question", "kind", "expected_behavior"],
}


def normalize(text: str) -> str:
    """Chuẩn hoá NFC + hạ chữ để so khớp key_fact với text chunk."""
    return unicodedata.normalize("NFC", text).lower()


def load_json(path: Path) -> list[dict]:
    """Đọc file nhãn — JSON mảng in dọc."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"[{path.name}] JSON hỏng: {exc}") from exc


def main() -> int:
    chunks = {c["chunk_id"]: c for c in json.load(CHUNKS_PATH.open(encoding="utf-8"))}
    errors: list[str] = []
    warnings: list[str] = []
    seen_ids: set[str] = set()

    for filename, required in REQUIRED_FIELDS.items():
        path = EVAL_DIR / filename
        if not path.exists():
            errors.append(f"THIẾU FILE: {filename}")
            continue
        rows = load_json(path)
        print(f"{filename}: {len(rows)} item")

        for row in rows:
            item_id = row.get("id", "<không có id>")
            tag = f"[{filename}:{item_id}]"

            for field in required:
                if field not in row:
                    errors.append(f"{tag} thiếu field bắt buộc `{field}`")

            if item_id in seen_ids:
                errors.append(f"{tag} id bị trùng")
            seen_ids.add(item_id)

            all_ids = row.get("gold_chunk_ids", []) + row.get("supporting_chunk_ids", [])
            all_ids += row.get("hop1_chunk_ids", []) + row.get("hop2_chunk_ids", [])
            for cid in all_ids:
                if cid not in chunks:
                    errors.append(f"{tag} chunk_id không tồn tại: {cid}")

            gold_text = normalize(
                " ".join(chunks[c]["text"] for c in row.get("gold_chunk_ids", []) if c in chunks)
            )
            support_text = normalize(
                " ".join(chunks[c]["text"] for c in row.get("supporting_chunk_ids", []) if c in chunks)
            )
            for fact in row.get("key_facts", []):
                if normalize(fact) not in gold_text and normalize(fact) not in support_text:
                    warnings.append(f"{tag} key_fact không khớp nguyên văn chunk: {fact!r}")

            if row.get("expected_step_count") == 2 and filename == "retrieval_qa.json":
                if not row.get("hop1_chunk_ids") or not row.get("hop2_chunk_ids"):
                    errors.append(f"{tag} multi-hop nhưng thiếu hop1_chunk_ids/hop2_chunk_ids")
                if row.get("single_chunk_contains_both") is not False:
                    errors.append(f"{tag} multi-hop phải khai single_chunk_contains_both=false")

    print()
    for w in warnings:
        print(f"CẢNH BÁO {w}")
    for e in errors:
        print(f"LỖI     {e}")
    print(f"\n{len(errors)} lỗi, {len(warnings)} cảnh báo, {len(seen_ids)} item tổng cộng.")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
