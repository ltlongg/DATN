"""Test `orchestrator/planning.py` — chuẩn hoá todo list + guard entity (§2.1). Thuần, không mock."""

from __future__ import annotations

from app.orchestrator.planning import DEFAULT_STEP_LABEL, normalize_plan
from app.schemas.ask import PlanOutput, PlanStep, StepQuery


def _out(**kw) -> PlanOutput:
    kw.setdefault("standalone_query", "standalone q")
    kw.setdefault("route", "needs_retrieval")
    return PlanOutput(**kw)


def _norm(parsed: PlanOutput, question: str, *, max_steps=1, max_queries=4):
    return normalize_plan(
        parsed, question, max_steps=max_steps, max_queries_per_step=max_queries
    )


# --- fallback: steps rỗng -> 1 bước từ standalone_query ---


def test_empty_steps_builds_default_step() -> None:
    standalone, steps, warnings = _norm(_out(), "Trương Định là ai?")
    assert standalone == "standalone q"
    assert len(steps) == 1
    assert steps[0].label == DEFAULT_STEP_LABEL
    assert [q.query for q in steps[0].queries] == ["standalone q"]
    assert warnings == []


def test_blank_standalone_falls_back_to_question() -> None:
    standalone, steps, _ = _norm(_out(standalone_query="   "), "Câu hỏi gốc?")
    assert standalone == "Câu hỏi gốc?"
    assert steps[0].queries[0].query == "Câu hỏi gốc?"


def test_step_with_only_blank_queries_falls_back() -> None:
    parsed = _out(steps=[PlanStep(id=1, label="L", queries=[StepQuery(query="  ")])])
    _, steps, _ = _norm(parsed, "hỏi")
    assert [q.query for q in steps[0].queries] == ["standalone q"]


# --- guard entity: chỉ giữ tên có NGUYÊN VĂN trong câu hỏi hiện tại ---


def test_entity_present_in_question_is_kept() -> None:
    parsed = _out(mentioned_entities=["Trương Định"])
    _, steps, warnings = _norm(parsed, "Trương Định hy sinh năm nào?")
    assert steps[0].queries[0].entities == ["Trương Định"]
    assert warnings == []


def test_entity_absent_from_question_is_dropped_with_warning() -> None:
    # Ca kinh điển: LLM suy đúng từ history, nhưng luật §2.1 vẫn cấm.
    parsed = _out(mentioned_entities=["Trương Định"])
    _, steps, warnings = _norm(parsed, "Ông ấy làm gì?")
    assert steps[0].queries[0].entities == []
    assert any("entity" in w for w in warnings)


def test_entity_matching_ignores_case_and_extra_space() -> None:
    parsed = _out(mentioned_entities=["  trương   định  "])
    _, steps, _ = _norm(parsed, "Trương Định hy sinh năm nào?")
    assert steps[0].queries[0].entities == ["trương   định"]


def test_entity_matching_keeps_vietnamese_diacritics_strict() -> None:
    """CỐ Ý không bỏ dấu: "Truong Dinh" KHÔNG được coi là khớp "Trương Định"."""
    parsed = _out(mentioned_entities=["Truong Dinh"])
    _, steps, _ = _norm(parsed, "Trương Định hy sinh năm nào?")
    assert steps[0].queries[0].entities == []


def test_model_invented_entity_is_dropped() -> None:
    """Câu hỏi nhắc "Yên Thế" nhưng không nhắc "Đề Thám" -> tên model tự thêm bị loại."""
    parsed = _out(
        steps=[
            PlanStep(
                id=1,
                label="L",
                queries=[StepQuery(query="q", entities=["Yên Thế", "Đề Thám"])],
            )
        ]
    )
    _, steps, warnings = _norm(parsed, "Nghĩa quân Yên Thế đình chiến mấy lần?")
    assert steps[0].queries[0].entities == ["Yên Thế"]
    assert any("entity" in w for w in warnings)


def test_global_entities_union_into_every_query() -> None:
    parsed = _out(
        mentioned_entities=["Yên Thế"],
        steps=[
            PlanStep(
                id=1,
                label="L",
                queries=[
                    StepQuery(query="q1", entities=["Đề Nắm"]),
                    StepQuery(query="q2"),
                ],
            )
        ],
    )
    _, steps, _ = _norm(parsed, "Đề Nắm và Yên Thế?")
    assert steps[0].queries[0].entities == ["Đề Nắm", "Yên Thế"]
    assert steps[0].queries[1].entities == ["Yên Thế"]


def test_duplicate_entities_deduped_keeping_order() -> None:
    parsed = _out(
        mentioned_entities=["Yên Thế"],
        steps=[
            PlanStep(
                id=1, label="L", queries=[StepQuery(query="q", entities=["Yên Thế", "yên thế"])]
            )
        ],
    )
    _, steps, _ = _norm(parsed, "Yên Thế ra sao?")
    assert steps[0].queries[0].entities == ["Yên Thế"]


# --- cap: số bước + số query ---


def test_extra_steps_cut_with_warning() -> None:
    parsed = _out(
        steps=[
            PlanStep(id=1, label="A", queries=[StepQuery(query="q1")]),
            PlanStep(id=2, label="B", queries=[StepQuery(query="q2")]),
        ]
    )
    _, steps, warnings = _norm(parsed, "hỏi", max_steps=1)
    assert [s.label for s in steps] == ["A"]
    assert any("bước" in w for w in warnings)


def test_extra_queries_cut_to_max() -> None:
    parsed = _out(
        steps=[
            PlanStep(
                id=1, label="A", queries=[StepQuery(query=f"q{i}") for i in range(5)]
            )
        ]
    )
    _, steps, _ = _norm(parsed, "hỏi", max_queries=2)
    assert [q.query for q in steps[0].queries] == ["q0", "q1"]


def test_step_ids_renumbered_from_one() -> None:
    """LLM hay trả id lệch; bậc B4 tham chiếu id qua placeholder nên phải liền mạch."""
    parsed = _out(
        steps=[
            PlanStep(id=7, label="A", queries=[StepQuery(query="q1")]),
            PlanStep(id=9, label="B", queries=[StepQuery(query="q2")]),
        ]
    )
    _, steps, _ = _norm(parsed, "hỏi", max_steps=2)
    assert [s.id for s in steps] == [1, 2]


def test_blank_label_falls_back_to_default() -> None:
    parsed = _out(steps=[PlanStep(id=1, label="   ", queries=[StepQuery(query="q")])])
    _, steps, _ = _norm(parsed, "hỏi")
    assert steps[0].label == DEFAULT_STEP_LABEL
