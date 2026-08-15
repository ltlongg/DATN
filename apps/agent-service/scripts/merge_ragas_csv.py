"""Ghép kết quả chấm lại của vài câu vào bảng điểm đầy đủ — bước 3 (tùy chọn).

`run_ragas_eval.py --ids qa-046 qa-083` chỉ chấm đúng mấy câu được nêu và ghi ra một CSV
riêng. Script này vá những dòng đó vào bảng đầy đủ (`<runs>.ragas.csv`) để không phải trả
tiền chấm lại cả 100 câu chỉ vì vài câu hỏng.

Khớp dòng theo cột `id`. Bảng đầy đủ sinh trước 2026-08-10 chưa có cột đó, nên khi thiếu
thì script suy ra id từ `user_input` bằng file nhãn — và ghi luôn cột `id` vào output để
lần sau khỏi phải suy.

Với mỗi id được vá, MỌI cột có trong file patch đều ghi đè lên bảng gốc (kể cả `response`,
`retrieved_contexts` — sau khi chạy lại thì text cũng mới). Cột chỉ có ở bảng gốc thì giữ
nguyên, và đó chính là chỗ dễ sai: patch chỉ chấm một metric trong khi text đã đổi thì các
metric còn lại vẫn là điểm của câu trả lời CŨ. Gặp ca đó script cảnh báo và bắt phải nêu rõ
`--allow-stale`.

Mặc định ghi ra file mới `<base>.merged.csv`; muốn đè thẳng bảng gốc thì `--in-place`.

Dùng (chạy trong venv agent-service, từ apps/agent-service):

    python -m scripts.merge_ragas_csv --patch ../../dataset/eval/runs/auto.ids5.csv
    python -m scripts.merge_ragas_csv --patch ... --in-place
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[3]
EVAL_DIR = ROOT / "dataset" / "eval"
TEXT_COLUMNS = ("user_input", "retrieved_contexts", "response", "reference")


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise SystemExit(f"Không có file: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def ensure_id_column(frame: pd.DataFrame, dataset: str, label: str) -> pd.DataFrame:
    """Thêm cột `id` nếu thiếu, suy từ `user_input` qua file nhãn."""
    if "id" in frame.columns:
        return frame

    labels = json.loads((EVAL_DIR / dataset).read_text(encoding="utf-8"))
    by_question: dict[str, str] = {}
    for item in labels:
        if item["question"] in by_question:
            raise SystemExit(
                f"Bộ nhãn có hai câu hỏi trùng chữ ({item['id']} và "
                f"{by_question[item['question']]}) — không suy id từ text được."
            )
        by_question[item["question"]] = item["id"]

    ids = frame["user_input"].map(by_question)
    if ids.isna().any():
        missing = frame.loc[ids.isna(), "user_input"].head(3).tolist()
        raise SystemExit(
            f"{label}: {int(ids.isna().sum())} dòng không tra được id từ bộ nhãn "
            f"`{dataset}`. Ví dụ: {missing}"
        )
    frame = frame.copy()
    frame.insert(0, "id", ids)
    return frame


def find_stale_metrics(
    base: pd.DataFrame, patch: pd.DataFrame, ids: list[str]
) -> dict[str, list[str]]:
    """Id nào có text đổi mà lại còn metric không được chấm lại."""
    untouched = [
        c
        for c in base.columns
        if c not in patch.columns and c != "id" and c not in TEXT_COLUMNS
    ]
    if not untouched:
        return {}

    base_by_id = base.set_index("id")
    patch_by_id = patch.set_index("id")
    stale = {}
    for row_id in ids:
        changed = [
            c
            for c in TEXT_COLUMNS
            if c in patch.columns
            and c in base.columns
            and str(base_by_id.at[row_id, c]) != str(patch_by_id.at[row_id, c])
        ]
        if changed:
            stale[row_id] = untouched
    return stale


def merge(base: pd.DataFrame, patch: pd.DataFrame) -> tuple[pd.DataFrame, list[str], list[str]]:
    """Vá `patch` lên `base` theo id. Trả (kết quả, id đã vá, id thêm mới)."""
    merged = base.set_index("id")
    patched, added = [], []
    for row_id, row in patch.set_index("id").iterrows():
        if row_id in merged.index:
            for column, value in row.items():
                if column not in merged.columns:
                    merged[column] = pd.NA
                merged.at[row_id, column] = value
            patched.append(row_id)
        else:
            merged.loc[row_id] = row
            added.append(row_id)
    return merged.reset_index(), patched, added


def report_changes(
    base: pd.DataFrame, merged: pd.DataFrame, patch: pd.DataFrame, ids: list[str]
) -> None:
    """In điểm trước/sau cho từng id được vá — số này để đưa thẳng vào báo cáo."""
    metric_columns = [
        c for c in patch.columns if c != "id" and c not in TEXT_COLUMNS
    ]
    before = base.set_index("id")
    after = merged.set_index("id")
    for row_id in ids:
        parts = []
        for column in metric_columns:
            old = before.at[row_id, column] if column in before.columns else None
            new = after.at[row_id, column]
            parts.append(f"{column}: {old} -> {new}")
        print(f"  {row_id}  " + " | ".join(parts))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--patch", required=True, help="CSV do `run_ragas_eval.py --ids` sinh")
    ap.add_argument(
        "--base",
        default=str(EVAL_DIR / "runs" / "auto.ragas.csv"),
        help="bảng điểm đầy đủ cần vá",
    )
    ap.add_argument("--dataset", default="retrieval_qa.json", help="file nhãn để suy id")
    ap.add_argument("--out", default=None, help="mặc định: <base>.merged.csv")
    ap.add_argument("--in-place", action="store_true", help="đè thẳng lên --base")
    ap.add_argument(
        "--allow-stale",
        action="store_true",
        help="chấp nhận việc text đổi nhưng vài metric không được chấm lại",
    )
    args = ap.parse_args()

    base_path = Path(args.base)
    base = ensure_id_column(read_csv(base_path), args.dataset, "base")
    patch = ensure_id_column(read_csv(Path(args.patch)), args.dataset, "patch")

    duplicated = patch["id"][patch["id"].duplicated()].tolist()
    if duplicated:
        raise SystemExit(f"File patch có id trùng: {duplicated}")

    known = [i for i in patch["id"] if i in set(base["id"])]
    stale = find_stale_metrics(base, patch, known)
    if stale and not args.allow_stale:
        lines = "\n".join(f"  {k}: {', '.join(v)}" for k, v in stale.items())
        raise SystemExit(
            "DỪNG: những câu này có text mới nhưng các metric sau vẫn là điểm của câu trả "
            f"lời cũ:\n{lines}\n"
            "Chấm lại đủ metric cho chúng, hoặc chạy lại với `--allow-stale` nếu bạn cố ý."
        )

    merged, patched, added = merge(base, patch)

    print(f"Vá {len(patched)} dòng" + (f", thêm mới {len(added)}: {added}" if added else ""))
    report_changes(base, merged, patch, patched)

    out_path = base_path if args.in_place else Path(args.out or base_path.with_suffix(".merged.csv"))
    merged.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"-> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
