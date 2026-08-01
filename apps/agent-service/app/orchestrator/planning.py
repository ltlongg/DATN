"""Chuẩn hoá + kiểm tra todo list do `plan` (LLM) sinh ra. THUẦN: không I/O, không LLM.

Tách khỏi `nodes.py` để test được không cần mock gì. Nguyên tắc xuyên suốt: **không tin
output LLM** — sai luật thì hạ về phương án đơn giản nhất (1 bước, 1 query từ
`standalone_query`) kèm warning, thà chạy đơn giản còn hơn chạy sai.

Luật `entities` (docs/plan/agentic-retrieval-loop-plan.md §2.1) cưỡng chế TẠI ĐÂY chứ không
chỉ bằng prompt: chỉ giữ tên riêng xuất hiện NGUYÊN VĂN trong câu hỏi hiện tại. Không lấy từ
lịch sử hội thoại, không lấy từ kiến thức nội tại của model — model nhớ sai tên thì seed sai
đi thẳng vào graph mà không ai biết.
"""

from __future__ import annotations

import unicodedata

from app.schemas.ask import PlanOutput, PlanStep, StepQuery

__all__ = ["normalize_plan", "DEFAULT_STEP_LABEL"]

DEFAULT_STEP_LABEL = "Tìm trong tài liệu"


def _fold(text: str) -> str:
    """Chuẩn hoá để so khớp literal: NFC + lower + gộp khoảng trắng.

    CỐ Ý giữ nguyên dấu tiếng Việt — bỏ dấu sẽ làm "Đại" khớp "Dại", tức nới guard ra đúng
    chỗ nó cần chặt. NFC vì cùng một chữ có dấu gõ hai kiểu ra hai chuỗi byte khác nhau.
    """
    return " ".join(unicodedata.normalize("NFC", text).lower().split())


def _keep_grounded_entities(entities: list[str], *, folded_question: str) -> list[str]:
    """Giữ entity xuất hiện nguyên văn trong câu hỏi; bỏ phần còn lại. Dedupe, giữ thứ tự."""
    kept: list[str] = []
    seen: set[str] = set()
    for raw in entities:
        name = raw.strip()
        folded = _fold(name)
        if not folded or folded in seen or folded not in folded_question:
            continue
        seen.add(folded)
        kept.append(name)
    return kept


def _clean_queries(
    queries: list[StepQuery],
    *,
    folded_question: str,
    global_entities: list[str],
    max_queries: int,
) -> tuple[list[StepQuery], int]:
    """Lọc query rỗng, gắn seed toàn cục, cắt còn `max_queries`.

    Trả kèm số entity bị loại để node ghi warning (loại IM LẶNG thì không đo được §10).
    """
    cleaned: list[StepQuery] = []
    dropped = 0
    for item in queries:
        text = item.query.strip()
        if not text:
            continue
        grounded = _keep_grounded_entities(item.entities, folded_question=folded_question)
        dropped += len(item.entities) - len(grounded)
        # Seed toàn cục (`mentioned_entities`) union vào MỌI query — chúng đã qua cùng guard.
        merged = list(dict.fromkeys([*grounded, *global_entities]))
        cleaned.append(StepQuery(query=text, entities=merged))
    return cleaned[:max_queries], dropped


def normalize_plan(
    parsed: PlanOutput,
    question: str,
    *,
    max_steps: int,
    max_queries_per_step: int,
) -> tuple[str, list[PlanStep], list[str]]:
    """LLM output -> (standalone_query, steps đã kiểm, warnings).

    `steps` rỗng / mọi query rỗng -> dựng 1 bước mặc định từ `standalone_query`: đây là
    hành vi TRƯỚC khi có multi-query, nên fallback không làm hồi quy điều gì.
    """
    warnings: list[str] = []
    standalone = parsed.standalone_query.strip() or question
    folded_question = _fold(question)

    global_entities = _keep_grounded_entities(
        parsed.mentioned_entities, folded_question=folded_question
    )
    dropped = len(parsed.mentioned_entities) - len(global_entities)

    steps: list[PlanStep] = []
    for index, step in enumerate(parsed.steps[:max_steps], start=1):
        queries, step_dropped = _clean_queries(
            step.queries,
            folded_question=folded_question,
            global_entities=global_entities,
            max_queries=max_queries_per_step,
        )
        dropped += step_dropped
        if not queries:
            continue
        # id đánh lại theo thứ tự chạy: LLM hay trả id lệch (0-based, nhảy số) và bước sau
        # sẽ tham chiếu id này qua placeholder (bậc B4), nên phải liền mạch từ 1.
        steps.append(
            PlanStep(id=index, label=step.label.strip() or DEFAULT_STEP_LABEL, queries=queries)
        )
    if len(parsed.steps) > max_steps:
        warnings.append(
            f"plan trả {len(parsed.steps)} bước, chỉ chạy {max_steps} bước đầu."
        )

    if not steps:
        steps = [
            PlanStep(
                id=1,
                label=DEFAULT_STEP_LABEL,
                queries=[StepQuery(query=standalone, entities=global_entities)],
            )
        ]
    if dropped:
        warnings.append(
            f"loại {dropped} entity không có nguyên văn trong câu hỏi (luật seed §2.1)."
        )
    return standalone, steps, warnings
