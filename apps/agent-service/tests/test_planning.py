"""Test `orchestrator/planning.py` — chuẩn hoá todo list + guard entity. Thuần, không mock."""

from __future__ import annotations

from app.orchestrator.planning import (
    DEFAULT_STEP_LABEL,
    fill_placeholders,
    normalize_plan,
)
from app.schemas.ask import PlanOutput, PlanStep, StepQuery

def _out(**kw) -> PlanOutput:
    kw.setdefault("standalone_query", "standalone q")
    kw.setdefault("route", "needs_retrieval")
    return PlanOutput(**kw)

def _norm(parsed: PlanOutput, question: str, *, max_steps=2, max_queries=4):
    return normalize_plan(
        parsed, question, max_steps=max_steps, max_queries_per_step=max_queries
    )

# --- thứ tự field PlanOutput: prompt `plan` dựa vào nó ---

def test_standalone_query_generated_before_entities_and_mode() -> None:
    """`standalone_query` PHẢI đứng trước `mentioned_entities` VÀ `selected_mode`.

    Prompt bắt model đọc chính câu nó vừa viết lại để trích entity và chọn mode. Structured
    Outputs sinh JSON theo đúng thứ tự property của schema, mà thứ tự đó = thứ tự khai báo
    field ở đây — nên hai trường sau chỉ "thấy" được câu viết lại nếu nó đã ra trước. Đảo thứ
    tự là prompt nói dối model mà KHÔNG có gì khác báo lỗi: output vẫn hợp lệ, seed và mode
    chỉ âm thầm kém đi.
    """
    order = list(PlanOutput.model_fields)
    assert order.index("standalone_query") < order.index("mentioned_entities")
    assert order.index("standalone_query") < order.index("selected_mode")

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

# --- guard entity: chỉ giữ tên có NGUYÊN VĂN trong câu ĐÃ VIẾT LẠI ---

def test_entity_present_in_standalone_is_kept() -> None:
    parsed = _out(
        standalone_query="Trương Định hy sinh năm nào?",
        mentioned_entities=["Trương Định"],
    )
    _, steps, warnings = _norm(parsed, "Trương Định hy sinh năm nào?")
    assert steps[0].queries[0].entities == ["Trương Định"]
    assert warnings == []

def test_entity_resolved_from_history_is_kept_when_written_into_standalone() -> None:
    """Ca ĐẢO CHIỀU so với luật cũ, và là lý do đổi mốc.

    "Ông ấy hy sinh năm nào?" được viết lại thành "Trương Định hy sinh năm nào?" -> tên đó là
    seed HỢP LỆ dù câu người dùng gõ không hề có. Luật cũ (mốc = câu gốc) loại nó, và từ khi
    bỏ fallback token-match thì loại ở đây là mất seed hẳn chứ không còn ai gỡ lại.
    """
    parsed = _out(
        standalone_query="Trương Định hy sinh năm nào?",
        mentioned_entities=["Trương Định"],
    )
    _, steps, warnings = _norm(parsed, "Ông ấy hy sinh năm nào?")
    assert steps[0].queries[0].entities == ["Trương Định"]
    assert warnings == []

def test_entity_absent_from_standalone_is_dropped_with_warning() -> None:
    """Guard KHÔNG bị gỡ, chỉ đổi mốc: tên không có trong câu viết lại vẫn bị loại."""
    parsed = _out(standalone_query="Ông ấy làm gì?", mentioned_entities=["Trương Định"])
    _, steps, warnings = _norm(parsed, "Ông ấy làm gì?")
    assert steps[0].queries[0].entities == []
    assert any("entity" in w for w in warnings)

def test_entity_matching_ignores_case_and_extra_space() -> None:
    parsed = _out(
        standalone_query="Trương Định hy sinh năm nào?",
        mentioned_entities=["  trương   định  "],
    )
    _, steps, _ = _norm(parsed, "Trương Định hy sinh năm nào?")
    assert steps[0].queries[0].entities == ["trương   định"]

def test_entity_matching_keeps_vietnamese_diacritics_strict() -> None:
    """CỐ Ý không bỏ dấu: "Truong Dinh" KHÔNG được coi là khớp "Trương Định"."""
    parsed = _out(
        standalone_query="Trương Định hy sinh năm nào?",
        mentioned_entities=["Truong Dinh"],
    )
    _, steps, _ = _norm(parsed, "Trương Định hy sinh năm nào?")
    assert steps[0].queries[0].entities == []

def test_model_invented_entity_is_dropped() -> None:
    """Câu hỏi nhắc "Yên Thế" nhưng không nhắc "Đề Thám" -> tên model tự thêm bị loại."""
    parsed = _out(
        standalone_query="Nghĩa quân Yên Thế đình chiến mấy lần?",
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
        standalone_query="Đề Nắm và Yên Thế?",
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
        standalone_query="Yên Thế ra sao?",
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

# --- multi-step (B4): placeholder + resolve + depends_on ---

def _multihop(**overrides) -> PlanOutput:
    """Todo list multi-hop HỢP LỆ: bước 1 trích mắt xích, bước 2 dùng `<1>`."""
    steps = [
        PlanStep(
            id=1,
            label="Xác định người lãnh đạo",
            queries=[StepQuery(query="ai lãnh đạo Bắc Sơn", entities=["Bắc Sơn"])],
            resolve="tên người lãnh đạo",
        ),
        PlanStep(
            id=2,
            label="Chức vụ về sau",
            depends_on=1,
            queries=[StepQuery(query="<1> giữ chức vụ gì", entities=["<1>"])],
        ),
    ]
    overrides.setdefault("standalone_query", "Ai lãnh đạo Bắc Sơn về sau giữ chức gì?")
    return _out(steps=overrides.pop("steps", steps), **overrides)

def test_valid_multihop_plan_is_kept_intact() -> None:
    _, steps, warnings = _norm(_multihop(), "Ai lãnh đạo Bắc Sơn về sau giữ chức gì?")
    assert [s.id for s in steps] == [1, 2]
    assert steps[0].resolve == "tên người lãnh đạo"
    assert steps[1].depends_on == 1
    assert steps[1].queries[0].query == "<1> giữ chức vụ gì"
    assert warnings == []

def test_placeholder_in_entities_survives_literal_guard() -> None:
    """`<1>` KHÔNG có nguyên văn trong câu hỏi nhưng vẫn phải giữ: nó được điền ở
    execute-time. Guard chỉ cấm tên model tự nghĩ ra, không cấm placeholder."""
    _, steps, warnings = _norm(_multihop(), "Ai lãnh đạo Bắc Sơn về sau giữ chức gì?")
    assert steps[1].queries[0].entities == ["<1>"]
    assert warnings == []

def test_placeholder_in_first_step_downgrades_to_single_default_step() -> None:
    """Bước 1 không có gì để điền vào placeholder -> truy vấn rác. Hạ về câu hỏi gốc."""
    steps = [
        PlanStep(id=1, label="A", queries=[StepQuery(query="<1> là ai")]),
        PlanStep(id=2, label="B", queries=[StepQuery(query="q2")]),
    ]
    _, out, warnings = _norm(_multihop(steps=steps, standalone_query="standalone q"), "hỏi")
    assert len(out) == 1
    assert out[0].label == DEFAULT_STEP_LABEL
    assert out[0].queries[0].query == "standalone q"
    assert any("placeholder" in w for w in warnings)

def test_placeholder_pointing_to_step_without_resolve_downgrades() -> None:
    steps = [
        PlanStep(id=1, label="A", queries=[StepQuery(query="q1")]),  # không có resolve
        PlanStep(id=2, label="B", queries=[StepQuery(query="<1> làm gì")]),
    ]
    _, out, warnings = _norm(_multihop(steps=steps), "hỏi")
    assert [s.label for s in out] == ["A"]
    assert any("placeholder" in w for w in warnings)

def test_invalid_depends_on_is_cleared_not_downgraded() -> None:
    """`depends_on` không điều khiển gì lúc chạy (thứ tự là thứ tự `id`, chờ mắt xích là do
    placeholder) -> trỏ sai thì dọn field, KHÔNG vứt cả todo list chạy được."""
    steps = [
        PlanStep(id=1, label="A", depends_on=2, queries=[StepQuery(query="q1")]),
        PlanStep(id=2, label="B", queries=[StepQuery(query="q2")]),
    ]
    _, out, warnings = _norm(_multihop(steps=steps), "hỏi")
    assert [s.label for s in out] == ["A", "B"]
    assert out[0].depends_on is None
    assert any("depends_on" in w for w in warnings)

def test_resolve_nobody_consumes_is_stripped() -> None:
    """Trích xong không ai dùng = tốn đúng một LLM call vứt đi (§4.1 luật 5).

    Ca hay gặp nhất là bước CUỐI (không có bước nào sau để dùng), nhưng luật viết tổng quát
    theo "có ai tham chiếu `<id>` không" nên bắt luôn ca bước giữa bị bỏ quên.
    """
    steps = [
        PlanStep(id=1, label="A", queries=[StepQuery(query="q1")], resolve="mắt xích"),
        PlanStep(id=2, label="B", queries=[StepQuery(query="q2 không dùng placeholder")]),
    ]
    _, out, warnings = _norm(_multihop(steps=steps), "hỏi")
    assert [s.resolve for s in out] == ["", ""]
    assert any("resolve" in w for w in warnings)

def test_single_step_with_resolve_is_stripped_not_downgraded() -> None:
    parsed = _out(
        steps=[PlanStep(id=1, label="A", queries=[StepQuery(query="q")], resolve="x")]
    )
    _, out, _ = _norm(parsed, "hỏi")
    assert len(out) == 1 and out[0].resolve == ""

def test_renumbering_remaps_placeholder_and_depends_on() -> None:
    """LLM hay trả id lệch (0-based, nhảy số). Đánh số lại mà quên remap là placeholder trỏ
    vào hư không -> bước sau chạy với `<7>` nguyên văn trong truy vấn."""
    steps = [
        PlanStep(id=7, label="A", queries=[StepQuery(query="q1")], resolve="mắt xích"),
        PlanStep(
            id=9,
            label="B",
            depends_on=7,
            queries=[StepQuery(query="<7> làm gì", entities=["<7>"])],
        ),
    ]
    _, out, warnings = _norm(_multihop(steps=steps), "hỏi")
    assert [s.id for s in out] == [1, 2]
    assert out[1].depends_on == 1
    assert out[1].queries[0].query == "<1> làm gì"
    assert out[1].queries[0].entities == ["<1>"]
    assert warnings == []

def test_second_step_cut_by_max_steps_downgrades_orphaned_placeholder() -> None:
    """Cắt bước 2 vì quá `max_steps` thì `resolve` của bước 1 mất người tiêu thụ -> phải
    strip, không được để lại một LLM call vô nghĩa."""
    _, out, warnings = _norm(_multihop(), "hỏi", max_steps=1)
    assert len(out) == 1
    assert out[0].resolve == ""
    assert any("bước" in w for w in warnings)

# --- fill_placeholders (execute-time) ---

def test_fill_placeholders_replaces_in_query_and_entities() -> None:
    step = PlanStep(
        id=2,
        label="B",
        queries=[StepQuery(query="<1> giữ chức gì", entities=["<1>", "Bắc Sơn"])],
    )
    filled = fill_placeholders(step, {1: "Chu Văn Tấn"})
    assert filled.queries[0].query == "Chu Văn Tấn giữ chức gì"
    assert filled.queries[0].entities == ["Chu Văn Tấn", "Bắc Sơn"]

def test_fill_placeholders_leaves_step_untouched_when_nothing_to_fill() -> None:
    step = PlanStep(id=1, label="A", queries=[StepQuery(query="q", entities=["X"])])
    assert fill_placeholders(step, {}) is step
