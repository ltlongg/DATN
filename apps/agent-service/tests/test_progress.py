"""Test `orchestrator/progress.py` — dựng danh sách bước + dòng phụ panel tiến trình (B3).

Thuần, không mock gì: đây đúng là lý do tách module riêng thay vì nhét chuỗi vào nodes.
"""

from __future__ import annotations

import pytest

from app.orchestrator import progress
from app.schemas.ask import PlanStep, StepQuery


def _step(step_id: int, label: str, queries: list[str]) -> PlanStep:
    return PlanStep(
        id=step_id, label=label, queries=[StepQuery(query=q) for q in queries]
    )


# --- build_step_list ---


def test_needs_retrieval_list_is_plan_then_todos_then_synthesize_validate_then_viz() -> None:
    rows = progress.build_step_list("needs_retrieval", [_step(1, "Tìm A", ["q1"])])
    assert [r["id"] for r in rows] == [
        "plan",
        "todo:1",
        "synthesize:1",
        "validate:1",
        "visualization",
    ]
    assert [r["kind"] for r in rows] == ["system", "retrieve", "system", "system", "system"]
    assert rows[1]["label"] == "Tìm A"


def test_simple_question_has_exactly_five_rows() -> None:
    """Regression "không độn bước" (plan §7.3 mục 4): câu đơn đúng 5 dòng (1 + N + 2 + viz).
    Con số này phụ thuộc BẬC BUILD — B4 (multi-step) sẽ làm N > 1, sửa cùng lúc đó."""
    rows = progress.build_step_list("needs_retrieval", [_step(1, "Tìm", ["q"])])
    assert len(rows) == 5


def test_retry_appends_new_rows_instead_of_reusing_the_old_ones() -> None:
    """Người dùng phải THẤY được là hệ thống đã soạn lại (plan §7.3.1 mục 1) — ghi đè dòng
    cũ thì lần soạn lại biến mất khỏi lịch sử."""
    rows = progress.build_step_list(
        "needs_retrieval", [_step(1, "Tìm", ["q"])], attempts=2
    )
    assert [r["id"] for r in rows] == [
        "plan",
        "todo:1",
        "synthesize:1",
        "validate:1",
        "synthesize:2",
        "validate:2",
        "visualization",
    ]


def test_visualization_stays_last_when_retry_inserts_rows_in_the_middle() -> None:
    """Dựng bản đồ chạy SAU cùng; để nó lọt vào giữa thì panel kể sai thứ tự việc đã làm."""
    for attempts in (1, 2, 3):
        rows = progress.build_step_list(
            "needs_retrieval", [_step(1, "Tìm", ["q"])], attempts=attempts
        )
        assert rows[-1]["id"] == "visualization"


@pytest.mark.parametrize("route", ["ambiguous", "smalltalk", "out_of_scope"])
def test_non_retrieval_routes_have_only_plan_row(route) -> None:
    rows = progress.build_step_list(route, [_step(1, "Tìm", ["q"])])
    assert [r["id"] for r in rows] == ["plan"]


def test_list_rows_carry_no_state() -> None:
    """State đi riêng qua event `step` để cập nhật được nhiều lần; lẫn vào đây là hai
    nguồn sự thật cho cùng một thứ."""
    rows = progress.build_step_list("needs_retrieval", [_step(1, "Tìm", ["q"])])
    assert all(set(r) == {"id", "label", "kind"} for r in rows)


# --- plan_detail ---


def test_plan_detail_single_query() -> None:
    assert progress.plan_detail("needs_retrieval", [_step(1, "Tìm", ["q"])]) == (
        "Câu hỏi đơn · 1 bước"
    )


def test_plan_detail_counts_parallel_queries() -> None:
    detail = progress.plan_detail("needs_retrieval", [_step(1, "Tìm", ["q1", "q2", "q3"])])
    assert detail == "Tách 3 truy vấn · tìm song song"


def test_plan_detail_explains_why_it_stopped_for_non_retrieval_routes() -> None:
    assert progress.plan_detail("ambiguous", []) == "Câu hỏi chưa rõ · cần hỏi lại"
    assert progress.plan_detail("smalltalk", []) == "Câu xã giao · không cần tra tài liệu"
    assert progress.plan_detail("out_of_scope", []) == "Ngoài phạm vi tài liệu"


def test_plan_detail_leads_with_step_count_for_multihop() -> None:
    """Nhiều bước là thông tin đắt hơn số truy vấn song song — và là lời giải thích cho việc
    câu này chờ lâu hơn thường lệ."""
    steps = [_step(1, "Xác định mắt xích", ["q1", "q2"]), _step(2, "Tra tiếp", ["q3"])]
    assert progress.plan_detail("needs_retrieval", steps) == (
        "Phát hiện 2 ý phụ thuộc nhau · tra 2 bước"
    )


# --- retrieve ---


def test_retrieve_detail_names_the_backends_that_actually_ran() -> None:
    assert (
        progress.retrieve_detail("hybrid", query_count=1, chunk_count=8)
        == "Dense + BM25 + graph · 8 đoạn"
    )
    assert (
        progress.retrieve_detail("traditional", query_count=1, chunk_count=5)
        == "Dense + BM25 · 5 đoạn"
    )
    assert (
        progress.retrieve_detail("graph", query_count=1, chunk_count=3)
        == "Knowledge graph · 3 đoạn"
    )


def test_retrieve_detail_mentions_parallel_queries_only_when_more_than_one() -> None:
    assert "truy vấn song song" not in progress.retrieve_detail(
        "hybrid", query_count=1, chunk_count=8
    )
    assert (
        progress.retrieve_detail("hybrid", query_count=2, chunk_count=8)
        == "Dense + BM25 + graph · 2 truy vấn song song · 8 đoạn"
    )


def test_zero_chunks_is_partial_and_says_so() -> None:
    assert progress.retrieve_state(0) == "partial"
    assert (
        progress.retrieve_detail("hybrid", query_count=2, chunk_count=0)
        == "Không tìm thấy đoạn phù hợp"
    )


def test_some_chunks_is_done() -> None:
    assert progress.retrieve_state(1) == "done"


# --- resolve (B4) ---


def test_step_awaiting_resolve_stays_running_after_retrieval() -> None:
    """Tìm được đoạn mới xong nửa việc — tick xanh lúc `resolve_step` còn đang chạy là hiện
    "đã hoàn thành" cho việc chưa xong (§7.3.1 mục 4)."""
    assert progress.retrieve_state(8, awaiting_resolve=True) == "running"
    assert progress.retrieve_state(8, awaiting_resolve=False) == "done"


def test_step_awaiting_resolve_with_no_chunk_is_partial_not_running() -> None:
    """0 đoạn thì resolve không chạy nữa -> dòng phải chốt luôn, không treo spinner."""
    assert progress.retrieve_state(0, awaiting_resolve=True) == "partial"


def test_resolve_detail_names_the_link_it_found() -> None:
    assert progress.resolve_detail(label="Xác định người kế nhiệm", value="Đề Thám") == (
        "Xác định người kế nhiệm → Đề Thám"
    )


def test_resolve_missing_detail_says_what_was_not_found() -> None:
    assert progress.resolve_missing_detail("tên người kế nhiệm") == (
        "Chưa xác định được tên người kế nhiệm"
    )


def test_resolve_internals_show_the_ask_and_the_answer() -> None:
    rows = progress.resolve_internals(
        target="tên người", value="", confidence="thấp", sources=[], dropped=[]
    )
    assert [r["label"] for r in rows] == [
        "Cần trích",
        "Trích được",
        "Độ tin cậy",
        "Nguồn hợp lệ",
    ]
    assert rows[1]["value"] == "—"  # trích trượt vẫn phải đọc được, không để ô trống
    assert rows[3]["value"] == "—"


def test_resolve_internals_expose_fabricated_sources() -> None:
    """Mắt xích bị loại vì bịa nguồn nhìn y hệt ca "không tìm thấy gì" nếu không nêu id đã
    loại — mà hai ca đó cần xử lý khác nhau hẳn (một cái là model bịa, một cái là corpus thiếu).
    """
    rows = progress.resolve_internals(
        target="tên người",
        value="Chu Văn Tấn",
        confidence="cao",
        sources=[],
        dropped=["id-bia"],
    )
    assert rows[-1]["label"] == "Nguồn bịa (bị loại)"
    assert rows[-1]["value"] == "id-bia"


def test_resolve_internals_hide_dropped_row_when_nothing_dropped() -> None:
    rows = progress.resolve_internals(
        target="t", value="v", confidence="cao", sources=["c-1"], dropped=[]
    )
    assert all(r["label"] != "Nguồn bịa (bị loại)" for r in rows)


# --- synthesize ---


def test_synthesize_detail_reports_context_size_and_confidence() -> None:
    assert (
        progress.synthesize_detail(context_count=6, confidence="cao")
        == "Soạn từ 6 đoạn · độ tin cậy cao"
    )


def test_synthesize_detail_without_confidence() -> None:
    assert progress.synthesize_detail(context_count=6, confidence=None) == "Soạn từ 6 đoạn"


@pytest.mark.parametrize("confidence", ["thấp", "không đủ dữ liệu"])
def test_weak_confidence_is_partial_not_done(confidence) -> None:
    """Trả lời xong nhưng hệ thống không chắc -> KHÔNG được tick xanh (plan §7.3 mục 1)."""
    assert progress.synthesize_state(confidence) == "partial"


@pytest.mark.parametrize("confidence", ["cao", "vừa"])
def test_strong_confidence_is_done(confidence) -> None:
    assert progress.synthesize_state(confidence) == "done"


# --- validate (B5) ---


def test_validate_detail_says_matched_not_verified() -> None:
    """Chữ "xác minh" là overclaim: node chỉ kiểm id có thuộc tập truy hồi, KHÔNG kiểm câu
    văn có được đoạn đó chống lưng (plan §6 + §7.3 mục 2)."""
    detail = progress.validate_detail(valid=5, total=5, will_retry=False)
    assert detail == "5/5 liên kết nguồn hợp lệ"
    assert "xác minh" not in detail


def test_validate_detail_partial_does_not_say_soan_lai() -> None:
    """3/5 thì `after_validate` ĐI TIẾP, không soạn lại — viết "soạn lại" ở đây là mô tả sai
    luồng, đúng lỗi bản plan đầu mắc phải."""
    assert progress.validate_detail(valid=3, total=5, will_retry=False) == (
        "3/5 liên kết nguồn hợp lệ"
    )


def test_validate_detail_says_soan_lai_only_when_actually_retrying() -> None:
    assert progress.validate_detail(valid=0, total=5, will_retry=True) == (
        "0/5 liên kết nguồn hợp lệ · soạn lại"
    )
    # Hết lượt -> vẫn 0/5 nhưng KHÔNG soạn lại nữa.
    assert progress.validate_detail(valid=0, total=5, will_retry=False) == (
        "0/5 liên kết nguồn hợp lệ"
    )


def test_validate_detail_when_llm_named_no_source_at_all() -> None:
    assert progress.validate_detail(valid=0, total=0, will_retry=True) == (
        "Không có liên kết nguồn nào · soạn lại"
    )


def test_validate_state_partial_when_nothing_valid() -> None:
    assert progress.validate_state(0) == "partial"
    assert progress.validate_state(1) == "done"


# --- visualization ---


def test_visualization_detail_leads_with_timeline_not_markers() -> None:
    """Gazetteer đang hoãn -> marker gần như luôn 0. Dẫn bằng con số đó thì dòng phụ đọc như
    hệ thống hỏng, trong khi timeline vẫn dựng đủ (CLAUDE.md, honest fallback)."""
    detail = progress.visualization_detail(
        event_count=7, marker_count=0, timeline_count=5, unplaced=2
    )
    assert detail.startswith("5 mốc thời gian")
    assert "điểm trên bản đồ" not in detail
    assert "2 thiếu dữ liệu hiển thị" in detail


def test_visualization_detail_mentions_markers_when_there_are_any() -> None:
    assert (
        progress.visualization_detail(
            event_count=3, marker_count=3, timeline_count=3, unplaced=0
        )
        == "3 mốc thời gian · 3 điểm trên bản đồ"
    )


def test_no_matching_event_is_partial_and_says_so() -> None:
    assert progress.visualization_state(0) == "partial"
    assert progress.visualization_detail(
        event_count=0, marker_count=0, timeline_count=0, unplaced=0
    ) == "Không có sự kiện nào gắn với nguồn đã dùng"


def test_visualization_state_done_when_events_matched() -> None:
    assert progress.visualization_state(1) == "done"


# --- internals (tầng 2) ---


def _value(rows: list[dict[str, str]], label: str) -> str:
    return next(r["value"] for r in rows if r["label"] == label)


def test_plan_internals_spells_out_who_picked_the_mode() -> None:
    agent = progress.plan_internals(
        standalone_query="Ai ký hiệp định?",
        route="needs_retrieval",
        selected_mode="hybrid",
        mode_source="agent",
    )
    assert _value(agent, "Cách truy hồi") == "hybrid (agent chọn)"
    forced = progress.plan_internals(
        standalone_query="q", route="needs_retrieval", selected_mode="graph",
        mode_source="override",
    )
    assert _value(forced, "Cách truy hồi") == "graph (người dùng ép)"


def test_retrieve_internals_pairs_each_query_with_its_own_chunk_count() -> None:
    """Lý do gộp: DebugPanel cũ để câu truy vấn ở một mục, số đoạn ở mục khác — phải tự nhẩm
    mới biết truy vấn nào tách ra vô ích."""
    rows = progress.retrieve_internals(
        [
            {"query": "hiệp định Genève", "entities": [], "chunks": 8},
            {"query": "Pháp rút quân", "entities": ["Pháp"], "chunks": 0},
        ],
        total_chunks=8,
        graph_context=3,
    )
    assert _value(rows, "Truy vấn 1") == "hiệp định Genève  →  8 đoạn"
    assert _value(rows, "Truy vấn 2") == "Pháp rút quân  ·  seed: Pháp  →  0 đoạn"
    assert _value(rows, "Tổng đã gộp") == "8 đoạn"
    assert _value(rows, "Ngữ cảnh graph") == "3 quan hệ"


def test_synthesize_internals_explains_the_gap_between_retrieved_and_used() -> None:
    """"Truy hồi 12 đoạn" mà "soạn từ 9 đoạn" trông như mất đoạn; chunk provenance-only là
    lời giải thích, và trước đây nó không hiện ở đâu cả."""
    rows = progress.synthesize_internals(
        prompt_chunks=9, citation_only_chunks=3, model="gpt-5.4-nano", attempt=1
    )
    assert _value(rows, "Đoạn đưa vào prompt") == "9"
    assert _value(rows, "Đoạn chỉ để trích dẫn") == "3"
    assert _value(rows, "Model") == "gpt-5.4-nano"
    assert not any(r["label"] == "Lượt soạn" for r in rows)


def test_synthesize_internals_hides_noise_rows_when_they_say_nothing() -> None:
    rows = progress.synthesize_internals(
        prompt_chunks=9, citation_only_chunks=0, model="m", attempt=1
    )
    assert not any(r["label"] == "Đoạn chỉ để trích dẫn" for r in rows)


def test_synthesize_internals_marks_the_retry_attempt() -> None:
    rows = progress.synthesize_internals(
        prompt_chunks=9, citation_only_chunks=0, model="m", attempt=2
    )
    assert _value(rows, "Lượt soạn") == "lần 2"


def test_validate_internals_names_the_dropped_ids() -> None:
    """id bị loại = LLM nêu chunk không có trong tập vừa truy hồi. Đây là dấu hiệu bịa trích
    dẫn — lý do chính đáng nhất để giữ tầng 2 sau khi bỏ DebugPanel."""
    rows = progress.validate_internals(
        claimed=3, valid=1, dropped=["ghost-1", "ghost-2"], will_retry=False
    )
    assert _value(rows, "Bị loại") == "ghost-1, ghost-2"
    assert not any(r["label"] == "Hành động" for r in rows)


def test_validate_internals_shows_dash_and_retry_action() -> None:
    rows = progress.validate_internals(claimed=0, valid=0, dropped=[], will_retry=True)
    assert _value(rows, "Bị loại") == "—"
    assert _value(rows, "Hành động") == "soạn lại"
