"""Test render prompt plan + resolve + synthesize: history, graph_context có cấu trúc,
fact trung gian, retry suffix."""

from __future__ import annotations

from app.prompts import plan, resolve, synthesize
from app.prompts.synthesize import RETRY_INSTRUCTION
from app.schemas.ask import ChatMessage, ResolvedFact
from app.schemas.retrieval import GraphContextItem, RetrievedChunk

def _chunk(chunk_id: str, text: str, heading: list[str]) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id, text=text, metadata={}, heading_path=heading
    )

# --- plan ---

def test_plan_prompt_no_history() -> None:
    prompt = plan.build_user_prompt("Trương Định là ai?", [])
    assert "(không có)" in prompt
    assert "Trương Định là ai?" in prompt

def test_plan_prompt_renders_history_roles() -> None:
    history = [
        ChatMessage(role="user", content="Trương Định là ai?"),
        ChatMessage(role="assistant", content="Ông là thủ lĩnh kháng Pháp."),
    ]
    prompt = plan.build_user_prompt("Ông ấy làm gì sau đó?", history)
    assert "Người dùng: Trương Định là ai?" in prompt
    assert "Trợ lý: Ông là thủ lĩnh kháng Pháp." in prompt
    assert "Ông ấy làm gì sau đó?" in prompt

# --- synthesize ---

def test_synthesize_renders_chunk_with_heading_and_id() -> None:
    chunks = [_chunk("lichsu_clean-000042", "Nội dung đoạn.", ["II. Cần Vương", "2.1 Trương Định"])]
    prompt = synthesize.build_user_prompt("Hỏi gì đó?", chunks, [])
    assert "chunk_id: lichsu_clean-000042" in prompt
    assert "II. Cần Vương > 2.1 Trương Định" in prompt
    assert "Nội dung đoạn." in prompt

def test_synthesize_renders_relation_structurally() -> None:
    ctx = [
        GraphContextItem(
            kind="relation",
            source_name="Trương Định",
            target_name="Gò Công",
            keyword="hy sinh tại",
            description="Trương Định tự sát tại Gò Công năm 1864.",
            source_chunk_ids=["lichsu_clean-000043"],
        )
    ]
    prompt = synthesize.build_user_prompt("Trương Định hy sinh ở đâu?", [], ctx)
    assert "Trương Định -[hy sinh tại]-> Gò Công" in prompt
    assert "Mô tả: Trương Định tự sát tại Gò Công năm 1864." in prompt
    assert "(nguồn: lichsu_clean-000043)" in prompt

def test_synthesize_renders_entity_item() -> None:
    ctx = [
        GraphContextItem(
            kind="entity",
            name="Hồ Chí Minh",
            norm_name="hồ chí minh",
            description="Lãnh tụ cách mạng.",
            source_chunk_ids=["c-1"],
        )
    ]
    prompt = synthesize.build_user_prompt("Hồ Chí Minh là ai?", [], ctx)
    assert "- Hồ Chí Minh" in prompt
    assert "Mô tả: Lãnh tụ cách mạng." in prompt

def test_synthesize_retry_appends_instruction_only_when_retry() -> None:
    base = synthesize.build_user_prompt("q", [], [], is_retry=False)
    retry = synthesize.build_user_prompt("q", [], [], is_retry=True)
    assert RETRY_INSTRUCTION not in base
    assert RETRY_INSTRUCTION in retry

def test_synthesize_handles_empty_blocks_gracefully() -> None:
    prompt = synthesize.build_user_prompt("q", [], [])
    assert "(không có đoạn tài liệu)" in prompt
    assert "(không có quan hệ từ knowledge graph)" in prompt

# --- synthesize: fact trung gian từ multi-hop ---

def _fact(**kw) -> ResolvedFact:
    kw.setdefault("step_id", 1)
    kw.setdefault("label", "Xác định người lãnh đạo")
    kw.setdefault("value", "Chu Văn Tấn")
    kw.setdefault("confidence", "cao")
    kw.setdefault("source_chunk_ids", ["lichsu_clean-000103"])
    return ResolvedFact(**kw)

def test_synthesize_omits_fact_block_when_no_multihop() -> None:
    """Câu thường không có bước trích -> KHÔNG thêm khối rỗng vào prompt (tốn token + dạy
    model rằng khối đó luôn có)."""
    assert "[MẮT XÍCH ĐÃ XÁC ĐỊNH]" not in synthesize.build_user_prompt("q", [], [])

def test_synthesize_renders_fact_with_confidence_and_source() -> None:
    """Fact trung gian vào prompt như fact CÓ NGUỒN, không phải sự thật hiển nhiên (§0.2)."""
    prompt = synthesize.build_user_prompt("q", [], [], resolved_facts=[_fact()])
    assert "[MẮT XÍCH ĐÃ XÁC ĐỊNH]" in prompt
    assert "Chu Văn Tấn" in prompt
    assert "cao" in prompt
    assert "lichsu_clean-000103" in prompt

def test_synthesize_marks_unresolved_part_when_list_stopped_early() -> None:
    """Dừng list giữa chừng -> prompt phải nói rõ vế nào chưa tra được, không lấp liếm (§4.7)."""
    prompt = synthesize.build_user_prompt("q", [], [], unresolved="chức vụ về sau")
    assert "chức vụ về sau" in prompt
    assert "chưa" in prompt.lower()

# --- resolve ---

def test_resolve_prompt_contains_question_target_and_full_chunk_text() -> None:
    """Toàn văn chunk vào được vì output chỉ là một chuỗi ngắn — đây đúng là chỗ `reflect`
    (đã bỏ) làm sai khi chỉ đọc 240 ký tự đầu."""
    chunks = [_chunk("lichsu_clean-000103", "Chu Văn Tấn liên lạc với Xứ ủy.", ["Bắc Sơn"])]
    prompt = resolve.build_user_prompt("Ai lãnh đạo?", "tên người lãnh đạo chi bộ", chunks, [])
    assert "Ai lãnh đạo?" in prompt
    assert "tên người lãnh đạo chi bộ" in prompt
    assert "Chu Văn Tấn liên lạc với Xứ ủy." in prompt
    assert "chunk_id: lichsu_clean-000103" in prompt

def test_resolve_prompt_renders_graph_context() -> None:
    items = [
        GraphContextItem(
            kind="relation",
            keyword="lãnh đạo",
            description="Chu Văn Tấn lãnh đạo chi bộ Bắc Sơn.",
            source_name="Chu Văn Tấn",
            target_name="Bắc Sơn",
            source_chunk_ids=["lichsu_clean-000103"],
        )
    ]
    prompt = resolve.build_user_prompt("q", "mắt xích", [], items)
    assert "lãnh đạo" in prompt
    assert "Chu Văn Tấn" in prompt
