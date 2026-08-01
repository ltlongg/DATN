"""Chuẩn hoá + kiểm tra todo list do `plan` (LLM) sinh ra. THUẦN: không I/O, không LLM.

Tách khỏi `nodes.py` để test được không cần mock gì. Nguyên tắc xuyên suốt: **không tin
output LLM** — sai luật thì hạ về phương án đơn giản hơn (bỏ bước phụ thuộc, hoặc 1 bước 1
query từ `standalone_query`) kèm warning, thà chạy đơn giản còn hơn chạy sai.

Luật `entities` (docs/plan/agentic-retrieval-loop-plan.md §2.1) cưỡng chế TẠI ĐÂY chứ không
chỉ bằng prompt: chỉ giữ tên riêng xuất hiện NGUYÊN VĂN trong câu hỏi hiện tại. Không lấy từ
lịch sử hội thoại, không lấy từ kiến thức nội tại của model — model nhớ sai tên thì seed sai
đi thẳng vào graph mà không ai biết. Ngoại lệ DUY NHẤT là placeholder `<N>`: nó chưa có giá
trị lúc plan chạy, và giá trị điền vào sau này đến từ chunk đã truy hồi chứ không từ trí nhớ
model.

Module này cũng là nơi ĐỊNH NGHĨA cú pháp placeholder (`<N>`) — cả bên kiểm (plan-time) lẫn
bên điền (`fill_placeholders`, execute-time trong node `retrieve`) đều đọc từ đây, để không
có hai nơi cùng hiểu một cú pháp theo hai kiểu.
"""

from __future__ import annotations

import re
import unicodedata

from app.schemas.ask import PlanOutput, PlanStep, StepQuery

__all__ = ["normalize_plan", "fill_placeholders", "DEFAULT_STEP_LABEL"]

DEFAULT_STEP_LABEL = "Tìm trong tài liệu"

_PLACEHOLDER_RE = re.compile(r"<(\d+)>")


def _fold(text: str) -> str:
    """Chuẩn hoá để so khớp literal: NFC + lower + gộp khoảng trắng.

    CỐ Ý giữ nguyên dấu tiếng Việt — bỏ dấu sẽ làm "Đại" khớp "Dại", tức nới guard ra đúng
    chỗ nó cần chặt. NFC vì cùng một chữ có dấu gõ hai kiểu ra hai chuỗi byte khác nhau.
    """
    return " ".join(unicodedata.normalize("NFC", text).lower().split())


def _placeholder_ids(step: PlanStep) -> set[int]:
    """Mọi id bước được tham chiếu trong bước này (cả `query` lẫn `entities`)."""
    found: set[int] = set()
    for item in step.queries:
        for text in (item.query, *item.entities):
            found.update(int(m) for m in _PLACEHOLDER_RE.findall(text))
    return found


def _keep_grounded_entities(entities: list[str], *, folded_question: str) -> list[str]:
    """Giữ entity xuất hiện nguyên văn trong câu hỏi (hoặc placeholder); bỏ phần còn lại."""
    kept: list[str] = []
    seen: set[str] = set()
    for raw in entities:
        name = raw.strip()
        folded = _fold(name)
        if not folded or folded in seen:
            continue
        if not _PLACEHOLDER_RE.fullmatch(name) and folded not in folded_question:
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


def _renumber(steps: list[PlanStep]) -> tuple[list[PlanStep], int]:
    """Đánh số lại id liền mạch từ 1, REMAP mọi tham chiếu tới id cũ, dọn `depends_on` sai.

    LLM hay trả id lệch (0-based, nhảy số), và bước bị loại vì query rỗng cũng làm thủng dãy.
    Đánh số lại mà quên remap thì `<7>` trỏ vào hư không: guard sẽ bắt được nhưng cái giá là
    hạ nguyên todo list hợp lệ về 1 bước.

    `depends_on` trỏ sai thì XOÁ chứ không hạ cả list (trả kèm số lần xoá để node ghi
    warning): field này KHÔNG điều khiển gì lúc chạy — thứ tự thực thi là thứ tự `id`, còn
    việc chờ mắt xích là do placeholder quyết. Vứt một todo list chạy được vì một field chỉ
    dùng để vẽ UI là phản ứng thái quá.
    """
    id_map = {step.id: index for index, step in enumerate(steps, start=1)}

    def remap(text: str) -> str:
        return _PLACEHOLDER_RE.sub(
            lambda m: f"<{id_map[int(m.group(1))]}>" if int(m.group(1)) in id_map else m.group(0),
            text,
        )

    out: list[PlanStep] = []
    cleared = 0
    for index, step in enumerate(steps, start=1):
        depends_on = id_map.get(step.depends_on) if step.depends_on is not None else None
        if depends_on is not None and depends_on >= index:
            depends_on = None
        if (step.depends_on is not None) and depends_on is None:
            cleared += 1
        out.append(
            step.model_copy(
                update={
                    "id": index,
                    "depends_on": depends_on,
                    "queries": [
                        StepQuery(query=remap(q.query), entities=[remap(e) for e in q.entities])
                        for q in step.queries
                    ],
                }
            )
        )
    return out, cleared


def _strip_unused_resolve(steps: list[PlanStep]) -> tuple[list[PlanStep], bool]:
    """Xoá `resolve` của bước không ai tham chiếu tới. Trả (steps, đã_xoá_gì_không).

    Trích một mắt xích rồi không ai dùng = tốn đúng một LLM call vứt đi (§4.1 luật 5). Luật
    gốc chỉ cấm `resolve` ở bước CUỐI; viết theo "có ai tham chiếu không" thì bắt luôn ca
    bước giữa bị bỏ quên, và ca bước cuối tự động rơi vào (không có bước nào sau nó).
    """
    referenced: set[int] = set()
    for step in steps:
        referenced |= _placeholder_ids(step)
    stripped = False
    out: list[PlanStep] = []
    for step in steps:
        if step.resolve and step.id not in referenced:
            step = step.model_copy(update={"resolve": ""})
            stripped = True
        out.append(step)
    return out, stripped


def _orphan_placeholder(steps: list[PlanStep]) -> str | None:
    """Lý do todo list KHÔNG chạy được, hoặc None nếu hợp lệ.

    Một placeholder chỉ hợp lệ khi bước nó trỏ tới đứng TRƯỚC và có `resolve` — luật đó bao
    luôn "bước 1 không được chứa placeholder" (bước 1 không có bước nào đứng trước). Đây
    chính là thứ ÉP bất biến "tới `resolve_step` thì đã tích luỹ ít nhất một lượt truy hồi";
    thiếu nó thì một plan hỏng vẫn chạy và bước sau truy vấn bằng chuỗi `<1>` nguyên văn.
    """
    for index, step in enumerate(steps):
        resolvable = {p.id for p in steps[:index] if p.resolve}
        orphan = _placeholder_ids(step) - resolvable
        if orphan:
            ids = ", ".join(f"<{i}>" for i in sorted(orphan))
            return f"placeholder {ids} không trỏ tới bước trước có trích mắt xích"
    return None


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
    for step in parsed.steps[:max_steps]:
        queries, step_dropped = _clean_queries(
            step.queries,
            folded_question=folded_question,
            global_entities=global_entities,
            max_queries=max_queries_per_step,
        )
        dropped += step_dropped
        if not queries:
            continue
        steps.append(
            step.model_copy(
                update={"label": step.label.strip() or DEFAULT_STEP_LABEL, "queries": queries}
            )
        )
    if len(parsed.steps) > max_steps:
        warnings.append(
            f"plan trả {len(parsed.steps)} bước, chỉ chạy {max_steps} bước đầu."
        )

    steps, cleared = _renumber(steps)
    if cleared:
        warnings.append(f"xoá {cleared} depends_on không trỏ tới bước trước đó.")
    reason = _orphan_placeholder(steps)
    if reason is not None:
        # Hạ về bước ĐẦU (giữ được truy vấn + seed đã dựng) thay vì vứt cả list. Bước đầu mà
        # chính nó chứa placeholder thì không chạy một mình được -> lúc đó mới quay hẳn về
        # câu hỏi gốc (danh sách rỗng, dựng bước mặc định ở dưới).
        warnings.append(f"todo list sai luật ({reason}), hạ về 1 bước.")
        steps = [] if _orphan_placeholder(steps[:1]) else steps[:1]

    steps, stripped = _strip_unused_resolve(steps)
    if stripped:
        warnings.append("bỏ resolve của bước không có bước sau dùng tới.")

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


def fill_placeholders(step: PlanStep, resolved: dict[int, str]) -> PlanStep:
    """Điền `<N>` bằng mắt xích đã trích (execute-time, trong node `retrieve`).

    Bằng CODE chứ không nhờ LLM: thay chuỗi là việc tất định, gọi LLM ở đây chỉ thêm một chỗ
    bịa. Trả về CHÍNH `step` khi không có gì để điền — câu thường (không placeholder) không
    phải trả giá copy.
    """
    if not resolved or not _placeholder_ids(step):
        return step

    def fill(text: str) -> str:
        return _PLACEHOLDER_RE.sub(
            lambda m: resolved.get(int(m.group(1)), m.group(0)), text
        )

    return step.model_copy(
        update={
            "queries": [
                StepQuery(query=fill(q.query), entities=[fill(e) for e in q.entities])
                for q in step.queries
            ]
        }
    )
