"""Chấm retrieval_qa_v2.json bằng năm metric RAGAS — bước 2.

Đọc `dataset/eval/retrieval_qa_v2.json` mặc định và runs do `collect_eval_runs.py` sinh ra
(output thật của hệ), ghép thành `ragas.EvaluationDataset` rồi gọi `ragas.evaluate()`.
Cả hai đều là JSON mảng in dọc.

Ánh xạ field (RAGAS làm việc trên TEXT, không biết chunk_id):

    user_input         <- question
    reference          <- gold_answer
    retrieved_contexts <- runs.retrieved_contexts
    response           <- runs.response

Năm metric, đều có bước LLM-judge:

    Faithfulness                     — câu trả lời có bịa ngoài context không
    ResponseRelevancy                — câu trả lời có đúng trọng tâm câu hỏi không
    LLMContextPrecisionWithReference — đoạn hữu ích có được xếp lên trên không
    LLMContextRecall                 — tra có đủ để dựng lại gold_answer không
    FactualCorrectness               — claim của câu trả lời khớp gold tới đâu

Hai metric recall hỏi hai câu khác hẳn: `LLMContextRecall` chấm khâu TRA
(gold_answer có nằm trong đống chunk tra về không), `FactualCorrectness` chấm
khâu TRẢ LỜI (câu hệ viết ra có khớp dữ kiện của gold không).

`FactualCorrectness` dùng mode="recall" để đo độ phủ dữ kiện trong gold_answer;
điểm này không phải factual F1. `sources` của v2 dùng để kiểm tra nhãn;
retrieved_contexts khi chấm luôn lấy từ lần chạy hệ thống, không lấy nguồn mẫu.

Prompt nội bộ của cả năm metric được nạp từ bản dịch tiếng Việt cố định trong
`scripts/ragas_prompts/` — xem `use_vietnamese_prompts()`.

Dùng (chạy trong venv agent-service, từ apps/agent-service):

    python -m scripts.run_ragas_eval --runs ../../dataset/eval/runs/auto_v2.json

Chấm lại riêng một metric (không nạp embedding model):

    python -m scripts.run_ragas_eval --runs ../../dataset/eval/runs/auto_v2.json \
        --metrics factual_correctness

Chấm lại riêng vài câu — câu vừa chạy lại, hoặc câu judge trả NaN — rồi vá vào bảng đầy đủ:

    python -m scripts.run_ragas_eval --runs ../../dataset/eval/runs/auto_v2.json \
        --ids qa-046 qa-083
    python -m scripts.merge_ragas_csv --dataset retrieval_qa_v2.json \
        --base ../../dataset/eval/runs/auto_v2.ragas.csv \
        --patch ../../dataset/eval/runs/auto_v2.ids2.csv

Chi phí: cả năm metric đều gọi LLM cho từng câu khi chấm. `FactualCorrectness` ở
`mode="recall"` decompose + verify theo cả hai chiều — ~4 call/câu, đắt nhất trong năm.
CSV kết quả có cột `id` ở đầu để vá lại được; xem `attach_ids()`.
"""

from __future__ import annotations

import argparse
import json
import sys
import typing as t
from pathlib import Path

if sys.platform == "win32":
    # PowerShell có thể gán CP1252 cho process Python, trong khi help/log của script
    # có tiếng Việt. Không ép UTF-8 thì ngay cả `--help` cũng có thể văng
    # UnicodeEncodeError trước khi bắt đầu chấm.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[3]
EVAL_DIR = ROOT / "dataset" / "eval"
# Nằm cạnh script chứ không nằm trong dataset/eval/ vì thư mục đó bị gitignore, mà prompt
# thì BẮT BUỘC phải vào git — đó là điều kiện để số liệu tái lập được.
PROMPTS_DIR = Path(__file__).resolve().parent / "ragas_prompts"

try:
    from ragas import EvaluationDataset, evaluate
    from ragas.dataset_schema import SingleTurnSample
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import (
        FactualCorrectness,
        Faithfulness,
        LLMContextPrecisionWithReference,
        LLMContextRecall,
        ResponseRelevancy,
    )
    from ragas.run_config import RunConfig
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        f"Thiếu/không tương thích ragas ({exc}).\n"
        "Cài: uv pip install 'ragas==0.4.3' datasets\n"
        "Script viết theo API ragas 0.4.3 (đã đối chiếu source). Bản 0.1.x khác hẳn."
    ) from exc

# --- dựng dataset cho RAGAS ---------------------------------------------------------

def load_json(path: Path) -> list[dict]:
    """Đọc file JSON mảng in dọc."""
    return json.loads(path.read_text(encoding="utf-8"))

def select_labels(labels: list[dict], ids: t.Sequence[str] | None) -> list[dict]:
    """Lọc nhãn theo danh sách id, giữ nguyên thứ tự trong file nhãn.

    Id không có trong bộ nhãn thì DỪNG chứ không bỏ qua: gõ nhầm một id mà vẫn chạy
    thì hoá đơn LLM vẫn mất, còn câu cần chấm lại thì không được chấm.
    """
    if not ids:
        return labels
    wanted = list(dict.fromkeys(ids))
    known = {item["id"] for item in labels}
    unknown = [i for i in wanted if i not in known]
    if unknown:
        raise SystemExit(f"Không có id này trong bộ nhãn: {unknown}")
    return [item for item in labels if item["id"] in set(wanted)]

def build_samples(labels: list[dict], runs: dict[str, dict]) -> tuple[list, list[str], list[str]]:
    """Ghép nhãn + output thật thành SingleTurnSample.

    Trả `(samples, ids, skipped)` — `ids` song song với `samples` để gắn lại cột `id`
    vào CSV kết quả, thứ mà `EvaluationDataset` của RAGAS không mang theo.
    """
    samples, ids, skipped = [], [], []
    for item in labels:
        run = runs.get(item["id"])
        if run is None or run.get("error"):
            skipped.append(item["id"])
            continue
        if run.get("question") != item["question"]:
            raise SystemExit(
                f"{item['id']}: câu hỏi trong runs không khớp dataset; "
                "hãy thu thập lại kết quả cho dataset hiện tại."
            )
        samples.append(
            SingleTurnSample(
                user_input=item["question"],
                response=run.get("response") or "",
                retrieved_contexts=run.get("retrieved_contexts") or [],
                reference=item["gold_answer"],
            )
        )
        ids.append(item["id"])
    return samples, ids, skipped

def attach_ids(frame, samples: list, ids: list[str]):
    """Chèn cột `id` vào đầu DataFrame kết quả.

    Ghép theo VỊ TRÍ, nhưng chỉ sau khi đã đối chiếu `user_input` của từng dòng với
    sample tương ứng. RAGAS không hứa giữ nguyên thứ tự dòng trong `to_pandas()`, nên
    lệch một dòng là gán nhầm điểm cho câu khác — thà dừng còn hơn ghi ra file sai.
    """
    if len(frame) != len(samples):
        raise SystemExit(
            f"RAGAS trả {len(frame)} dòng cho {len(samples)} mẫu — không gắn được id."
        )
    mismatched = [
        (i, ids[i])
        for i, sample in enumerate(samples)
        if frame.iloc[i]["user_input"] != sample.user_input
    ]
    if mismatched:
        raise SystemExit(
            f"Thứ tự dòng RAGAS trả về không khớp thứ tự mẫu (lệch tại {mismatched[:3]}) "
            "— không gắn được id."
        )
    frame.insert(0, "id", ids)
    return frame

# --- metric ------------------------------------------------------------------------

METRIC_NAMES = (
    "context_precision",
    "context_recall",
    "factual_correctness",
    "faithfulness",
    "answer_relevancy",
)

def build_metrics(llm, embeddings=None, selected: t.Iterable[str] | None = None) -> list:
    """Dựng các metric được chọn theo thứ tự cố định.

    `ResponseRelevancy` là metric duy nhất cần embeddings: nó sinh ngược N câu hỏi từ
    `response` rồi đo cosine với `user_input`, chứ không phải LLM chấm điểm trực tiếp.

    `FactualCorrectness` dùng claim-decomposition prompt tiếng Việt có độ bao phủ cao: mọi
    dữ kiện có thể kiểm chứng, kể cả dữ kiện sai, đều phải thành claim trước khi NLI kiểm
    tra. `atomicity`/`coverage` của class chỉ chọn example trong `__post_init__`; prompt
    trong repo được `use_vietnamese_prompts()` ghi đè sau đó.
    """
    selected_names = set(selected or METRIC_NAMES)
    unknown = selected_names - set(METRIC_NAMES)
    if unknown:
        raise ValueError(f"Metric không hợp lệ: {sorted(unknown)}")
    if "answer_relevancy" in selected_names and embeddings is None:
        raise ValueError("answer_relevancy cần embeddings")

    factories = {
        "context_precision": lambda: LLMContextPrecisionWithReference(llm=llm),
        "context_recall": lambda: LLMContextRecall(llm=llm),
        "factual_correctness": lambda: FactualCorrectness(llm=llm, mode="recall"),
        "faithfulness": lambda: Faithfulness(llm=llm),
        "answer_relevancy": lambda: ResponseRelevancy(llm=llm, embeddings=embeddings),
    }
    return [factories[name]() for name in METRIC_NAMES if name in selected_names]

def build_llm(model: str | None):
    """Bọc LLM cho metric.

    Ragas 0.4 gắn DeprecationWarning lên `LangchainLLMWrapper` và trỏ sang `llm_factory`,
    NHƯNG ở đây vẫn phải dùng wrapper cũ: `llm_factory` trả `InstructorBaseRagasLLM` —
    một ABC **tách biệt**, không kế thừa `BaseRagasLLM`, trong khi `MetricWithLLM.llm`
    khai báo đúng kiểu `Optional[BaseRagasLLM]`. Dùng `llm_factory` là sai kiểu, không
    phải hiện đại hơn. (Đã đối chiếu ragas/llms/base.py + ragas/metrics/base.py 0.4.3.)
    """
    from langchain_openai import ChatOpenAI

    from app.core.config import get_settings

    settings = get_settings()
    return LangchainLLMWrapper(
        ChatOpenAI(
            model=model or settings.llm_model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            reasoning_effort="low",
        )
    )

def build_embeddings(kind: str):
    """Embeddings cho `ResponseRelevancy`.

    `ResponseRelevancy` gọi giao diện LangChain `embed_query`/`embed_documents`. Lớp legacy
    `ragas.embeddings.HuggingfaceEmbeddings` không còn implement đủ abstract methods với
    langchain-core hiện tại, nên dùng adapter LangChain rồi bọc bằng wrapper của Ragas.

    Mặc định `local` dùng chính model embedding tiếng Việt của hệ — chấm ngữ nghĩa tiếng
    Việt bằng model tiếng Anh của OpenAI là so lệch thước đo.
    """
    from app.core.config import get_settings

    settings = get_settings()
    if kind == "openai":
        from langchain_openai import OpenAIEmbeddings

        return LangchainEmbeddingsWrapper(
            OpenAIEmbeddings(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
        )
    from langchain_community.embeddings import HuggingFaceEmbeddings

    from app.core.embedding import EMBEDDING_MAX_TOKENS

    embeddings = HuggingFaceEmbeddings(
        model_name=settings.embedding_model,
        model_kwargs={"local_files_only": True},
        encode_kwargs={"normalize_embeddings": True},
    )
    embeddings.client.max_seq_length = EMBEDDING_MAX_TOKENS
    return LangchainEmbeddingsWrapper(embeddings)

def use_vietnamese_prompts(metrics: list) -> None:
    """Nạp prompt tiếng Việt đã dịch sẵn ở `scripts/ragas_prompts/`.

    Prompt nội bộ của RAGAS mặc định tiếng Anh; để nguyên thì bước tách mệnh đề của
    Faithfulness/Context Recall chạy prompt tiếng Anh trên văn bản tiếng Việt — sai lệch
    có thật, không phải thủ tục.

    CỐ Ý KHÔNG dùng `metric.adapt_prompts()`: hàm đó gọi LLM dịch lại mỗi lần chạy, nên
    hai lần chấm cùng cấu hình dùng hai prompt khác nhau và số liệu không tái lập được.
    Nó cũng chỉ dịch `examples`, để nguyên `instruction` tiếng Anh trừ khi bật
    `adapt_instruction=True`. Bản dịch trong repo dịch cả hai, review được bằng mắt và
    diff được trong git.

    Thiếu file thì DỪNG, không âm thầm chấm bằng prompt tiếng Anh — điểm sẽ lệch mà không
    có gì báo.

    Tên file theo đúng quy ước của `PromptMixin.load_prompts`:
    `{metric.name}_{prompt_name}_{language}.json`.
    """
    for metric in metrics:
        try:
            prompts = metric.load_prompts(str(PROMPTS_DIR), language="vietnamese")
        except (ValueError, FileNotFoundError) as exc:
            raise SystemExit(
                f"Không nạp được prompt tiếng Việt cho `{metric.name}`: {exc}\n"
                f"Kiểm tra {PROMPTS_DIR}. Muốn chấm bằng prompt gốc tiếng Anh thì dùng "
                "`--prompt-lang english`."
            ) from exc
        metric.set_prompts(**prompts)
        print(f"  prompt tiếng Việt: {metric.name}")

def resolve_output_path(
    runs_path: Path,
    selected: t.Sequence[str],
    out: str | None,
    ids: t.Sequence[str] | None = None,
) -> Path:
    """Tạo tên output an toàn; chạy subset không được đè file đủ metric.

    Subset theo metric hay theo id đều phải ra tên khác `<runs>.ragas.csv`, vì file đó
    là bảng kết quả đầy đủ — không ghi đè bằng kết quả chỉ chấm một phần.
    """
    if out:
        return Path(out)
    parts = []
    if tuple(selected) != METRIC_NAMES:
        parts.extend(selected)
    if ids:
        parts.append(f"ids{len(list(ids))}")
    if not parts:
        return runs_path.with_suffix(".ragas.csv")
    return runs_path.with_name(f"{runs_path.stem}.{'.'.join(parts)}.csv")

# --- main ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True, help="file JSON do collect_eval_runs.py sinh")
    ap.add_argument("--dataset", default="retrieval_qa_v2.json", help="tên file nhãn v2 trong dataset/eval/")
    ap.add_argument("--embeddings", default="local", choices=["local", "openai"])
    ap.add_argument("--judge-model", default=None, help="mặc định: settings.llm_model")
    ap.add_argument("--prompt-lang", default="vietnamese", choices=["vietnamese", "english"],
                    help="vietnamese = nạp prompt đã dịch ở scripts/ragas_prompts (mặc định); "
                         "english = prompt gốc của thư viện. Cả hai đều không gọi LLM")
    ap.add_argument(
        "--metrics",
        nargs="+",
        choices=METRIC_NAMES,
        default=list(METRIC_NAMES),
        help="metric cần chấm; mặc định chấm cả năm. Dùng "
        "`--metrics factual_correctness` để chấm lại riêng metric đó",
    )
    ap.add_argument(
        "--ids",
        nargs="+",
        default=None,
        metavar="ID",
        help="chỉ chấm những câu này (vd: --ids qa-046 qa-083). Dùng để chấm lại câu "
        "vừa chạy lại hoặc câu bị NaN mà không phải trả tiền cho cả bộ",
    )
    ap.add_argument("--max-workers", type=int, default=4)
    ap.add_argument("--out", default=None, help="file CSV kết quả từng câu")
    args = ap.parse_args()

    all_labels = load_json(EVAL_DIR / args.dataset)
    labels = select_labels(all_labels, args.ids)
    runs = {r["id"]: r for r in load_json(Path(args.runs))}

    samples, ids, skipped = build_samples(labels, runs)
    if skipped:
        print(f"BỎ QUA {len(skipped)} câu (thiếu run hoặc run lỗi): {skipped[:10]}")
    if not samples:
        raise SystemExit("Không có mẫu nào để chấm.")
    print(f"Chấm {len(samples)}/{len(labels)} câu; metric: {', '.join(args.metrics)}")

    llm = build_llm(args.judge_model)
    embeddings = (
        build_embeddings(args.embeddings) if "answer_relevancy" in args.metrics else None
    )
    metrics = build_metrics(llm, embeddings=embeddings, selected=args.metrics)

    if args.prompt_lang == "vietnamese":
        use_vietnamese_prompts(metrics)

    result = evaluate(
        dataset=EvaluationDataset(samples=samples),
        metrics=metrics,
        run_config=RunConfig(max_workers=args.max_workers),
    )
    print("\n=== RAGAS ===")
    print(result)

    out = resolve_output_path(Path(args.runs), args.metrics, args.out, args.ids)
    attach_ids(result.to_pandas(), samples, ids).to_csv(
        out, index=False, encoding="utf-8-sig"
    )
    print(f"Chi tiết từng câu -> {out}")
    if args.ids:
        base = Path(args.runs).with_suffix(".ragas.csv")
        print(
            f'Ghép vào bảng đầy đủ: python -m scripts.merge_ragas_csv '
            f'--dataset "{args.dataset}" --base "{base}" --patch "{out}"'
        )
    return 0

if __name__ == "__main__":
    sys.exit(main())
