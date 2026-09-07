"""Chạy hệ trên retrieval_qa_v2.json và ghi output thô — bước 1.

Năm metric RAGAS cần 2 thứ chỉ có được khi CHẠY THẬT: `response` (câu trả lời hệ sinh ra)
và `retrieved_contexts` (các đoạn hệ tra được). Script này sinh ra chúng, và chỉ chúng —
bản ghi ra file đúng bốn field `id / question / response / retrieved_contexts` (thêm
`error` hoặc `blocked` khi câu đó không chạy bình thường).

Hai mức chạy:

- `full`: toàn bộ graph production (input guardrail + plan + retrieval + answer).
- `rag`: bỏ input guardrail, giữ plan/rewrite/multi-hop + retrieval + answer.

Gọi thẳng LangGraph (`get_graph().ainvoke`) chứ không qua HTTP `/ask`, vì hai lý do:

- `AskResponse` chỉ trả `citations` (các chunk ĐƯỢC TRÍCH DẪN) — đó là tập con của tập
  tra được, trong khi context precision/recall phải chấm trên toàn bộ `retrieval.chunks`.
- Không phải dựng server + `X-Internal-Key` chỉ để chấm offline.

Mỗi cấu hình ablation là một lần chạy với `--mode` khác nhau; kết quả ghi ra file JSON
mảng in dọc riêng để `run_ragas_eval.py` chấm và so.

Dùng (chạy trong venv của agent-service, từ thư mục apps/agent-service):

    python -m scripts.collect_eval_runs --mode hybrid \
        --out ../../dataset/eval/runs/hybrid_v2.json
    python -m scripts.collect_eval_runs --pipeline rag --mode auto \
        --out ../../dataset/eval/runs/auto_rag_v2.json
    python -m scripts.collect_eval_runs --pipeline rag --mode auto --resume \
        --out ../../dataset/eval/runs/auto_rag_v2.json

`--resume` đọc file output hiện có, giữ các câu đã chạy thành công và chỉ chạy lại câu
thiếu, có `error` hoặc `blocked`. Kết quả được checkpoint sau mỗi câu hoàn tất nên lần chạy
sau vẫn tiếp tục được nếu tiến trình bị dừng giữa chừng.

Cần Qdrant/Neo4j/Postgres đang chạy và `.env` đã cấu hình như khi chạy server thật.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from functools import lru_cache
from pathlib import Path
from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.orchestrator import nodes
from app.orchestrator.errors import GuardrailsBlocked
from app.orchestrator.graph import get_graph
from app.orchestrator.runner import prepare_state
from app.orchestrator.state import AgentState
from app.schemas.ask import AskRequest

ROOT = Path(__file__).resolve().parents[3]
EVAL_DIR = ROOT / "dataset" / "eval"
EvalPipeline = Literal["full", "rag"]
EvalMode = Literal["auto", "traditional", "hybrid"]

@lru_cache(maxsize=1)
def get_rag_graph() -> CompiledStateGraph:
    """Graph dành riêng cho eval: cùng wiring production nhưng bỏ input guardrail.

    Giữ nguyên plan/resolve vì đó là nơi tạo standalone query, entity seed cho GraphRAG và
    mắt xích multi-hop; bỏ chúng sẽ biến `hybrid` thành một retriever khác với production.
    """
    builder = StateGraph(AgentState)
    builder.add_node("plan", nodes.plan)
    builder.add_node("retrieve", nodes.retrieve)
    builder.add_node("resolve_step", nodes.resolve_step)
    builder.add_node("advance_step", nodes.advance_step)
    builder.add_node("synthesize", nodes.synthesize)
    builder.add_node("validate_citations", nodes.validate_citations)
    builder.add_node("honest_answer", nodes.honest_answer)
    builder.add_node("direct_response", nodes.direct_response)
    builder.add_node("clarify", nodes.clarify)
    builder.add_node("build_visualization", nodes.build_visualization)
    builder.add_edge(START, "plan")
    builder.add_conditional_edges(
        "plan",
        nodes.route_intent,
        ["retrieve", "clarify", "honest_answer", "direct_response"],
    )
    builder.add_conditional_edges(
        "retrieve",
        nodes.after_retrieve,
        ["resolve_step", "advance_step", "synthesize", "honest_answer"],
    )
    builder.add_conditional_edges(
        "resolve_step", nodes.after_resolve, ["advance_step", "synthesize", "honest_answer"]
    )
    builder.add_conditional_edges(
        "advance_step", nodes.after_advance, ["retrieve", "synthesize", "honest_answer"]
    )
    builder.add_edge("synthesize", "validate_citations")
    builder.add_conditional_edges(
        "validate_citations",
        nodes.after_validate,
        ["build_visualization", "synthesize", "honest_answer"],
    )
    builder.add_edge("clarify", END)
    builder.add_edge("direct_response", END)
    builder.add_edge("honest_answer", END)
    builder.add_edge("build_visualization", END)
    return builder.compile()

def load_json(path: Path) -> list[dict]:
    """Đọc file nhãn — JSON mảng in dọc."""
    return json.loads(path.read_text(encoding="utf-8"))

def write_rows(path: Path, rows_by_id: dict[str, dict]) -> None:
    """Checkpoint nguyên tử để file cũ không hỏng nếu tiến trình dừng lúc đang ghi."""
    rows = sorted(rows_by_id.values(), key=lambda row: row["id"])
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    temp_path.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temp_path.replace(path)

def can_resume(existing: dict | None, item: dict) -> bool:
    """Chỉ dùng lại kết quả thành công và vẫn thuộc đúng câu hỏi hiện tại."""
    return bool(
        existing
        and existing.get("question") == item["question"]
        and not existing.get("error")
        and not existing.get("blocked")
    )

async def run_one(item: dict, mode: EvalMode, pipeline: EvalPipeline = "full") -> dict:
    """Chạy 1 câu qua graph, trả bản ghi thô. Lỗi được GHI LẠI chứ không nuốt —
    một câu chết không được làm hỏng cả lần chạy, nhưng cũng không được biến mất."""
    request = AskRequest(
        question=item["question"],
        mode=mode,
        stream=False,
        debug=False,
    )
    try:
        graph = get_graph() if pipeline == "full" else get_rag_graph()
        final = await graph.ainvoke(
            await prepare_state(request), config={"configurable": {"emitter": None}}
        )
    except GuardrailsBlocked as blocked:
        return {
            "id": item["id"], "question": item["question"], "blocked": True,
            "response": blocked.safe_message, "retrieved_contexts": [],
        }
    except Exception as exc:  # noqa: BLE001 — ghi lại để biết câu nào hỏng, vì sao
        return {
            "id": item["id"], "question": item["question"],
            "error": f"{type(exc).__name__}: {exc}",
            "response": "", "retrieved_contexts": [],
        }

    retrieval = final.get("retrieval")
    return {
        "id": item["id"],
        "question": item["question"],
        "response": final.get("answer") or "",
        "retrieved_contexts": [c.text for c in (retrieval.chunks if retrieval else [])],
    }

async def main_async(args: argparse.Namespace) -> int:
    all_items = load_json(EVAL_DIR / args.dataset)
    items = all_items
    if args.limit:
        items = items[: args.limit]
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows_by_id: dict[str, dict] = {}
    if args.resume and out_path.exists():
        questions = {item["id"]: item["question"] for item in all_items}
        rows_by_id = {
            row["id"]: row
            for row in load_json(out_path)
            if row.get("id") in questions
            and row.get("question") == questions[row["id"]]
        }

    pending = [item for item in items if not can_resume(rows_by_id.get(item["id"]), item)]
    reused = len(items) - len(pending)
    if args.resume:
        print(f"Resume: giữ {reused} câu thành công, chạy {len(pending)} câu còn lại")

    sem = asyncio.Semaphore(args.concurrency)
    checkpoint_lock = asyncio.Lock()
    done = 0

    async def guarded(item: dict) -> dict:
        nonlocal done
        async with sem:
            row = await run_one(item, args.mode, args.pipeline)
            async with checkpoint_lock:
                rows_by_id[row["id"]] = row
                write_rows(out_path, rows_by_id)
                done += 1
                flag = "ERR " if row.get("error") else ("BLK " if row.get("blocked") else "    ")
                detail = f": {row['error']}" if row.get("error") else ""
                print(f"[{done}/{len(pending)}] {flag}{row['id']}{detail}", flush=True)
            return row

    await asyncio.gather(*(guarded(i) for i in pending))
    write_rows(out_path, rows_by_id)

    rows = list(rows_by_id.values())
    errors = [r for r in rows if r.get("error")]
    print(f"\nGhi {len(rows)} bản ghi vào {out_path}")
    if errors:
        print(f"CẢNH BÁO: {len(errors)} câu lỗi — KHÔNG chấm cho tới khi xử xong:")
        for r in errors[:10]:
            print(f"  {r['id']}: {r['error']}")
    return 1 if errors else 0

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="retrieval_qa_v2.json", help="tên file v2 trong dataset/eval/")
    ap.add_argument("--pipeline", default="full", choices=["full", "rag"],
                    help="full = graph production; rag = bỏ input guardrail")
    ap.add_argument("--mode", default="auto", choices=["auto", "traditional", "hybrid"])
    ap.add_argument("--out", required=True, help="file JSON kết quả (mảng in dọc)")
    ap.add_argument("--limit", type=int, default=0, help="chỉ chạy N câu đầu (để thử)")
    ap.add_argument("--resume", action="store_true",
                    help="giữ câu thành công trong file --out; chạy lại câu lỗi/blocked/thiếu")
    ap.add_argument("--concurrency", type=int, default=2,
                    help="số câu chạy song song. Để thấp — mỗi câu đã tốn nhiều LLM call.")
    return asyncio.run(main_async(ap.parse_args()))

if __name__ == "__main__":
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main())
