"""CLI: chạy tiền xử lý `lichsu.md` (hoặc file bất kỳ) trước khi chunk.

Ví dụ:
    python -m scripts.preprocess_dataset \
        --input ../../lichsu.md \
        --output ../../lichsu.clean.md

Hoặc chạy thử trên N ký tự đầu (dry-run, không ghi file):
    python -m scripts.preprocess_dataset --input ../../lichsu.md --limit 6000
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Cho phép chạy script trực tiếp (không qua `-m`) bằng cách add parent vào path.
_THIS_DIR = Path(__file__).resolve().parent
_APP_ROOT = _THIS_DIR.parent
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))

from app.indexing.preprocessing import preprocess_file, preprocess_text  # noqa: E402

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="File đầu vào (markdown/text).")
    parser.add_argument(
        "--output",
        default=None,
        help="File đầu ra. Nếu bỏ trống và không có --limit, sẽ ghi đè input với suffix .clean.md.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Chỉ xử lý N ký tự đầu (dry-run, không ghi file). 0 = toàn bộ.",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        parser.error(f"Input không tồn tại: {input_path}")

    if args.limit > 0:
        raw = input_path.read_text(encoding="utf-8")[: args.limit]
        cleaned, report = preprocess_text(raw)
        print(f"[dry-run] {input_path}, đọc {len(raw)} ký tự")
        print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
        print("--- preview (1000 ký tự đầu sau preprocess) ---")
        print(cleaned[:1000])
        return 0

    output_path = Path(args.output) if args.output else input_path.with_suffix(".clean.md")
    report = preprocess_file(input_path, output_path)
    print(f"Đã ghi: {output_path}")
    print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
