"""Test render prompt build_query + synthesize: history, graph_context có cấu trúc, retry suffix."""

from __future__ import annotations

from app.prompts import build_query, synthesize
from app.prompts.synthesize import RETRY_INSTRUCTION
from app.schemas.ask import ChatMessage
from app.schemas.retrieval import GraphContextItem, RetrievedChunk


def _chunk(chunk_id: str, text: str, heading: list[str]) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id, text=text, metadata={}, heading_path=heading
    )


# --- build_query ---


def test_build_query_no_history() -> None:
    prompt = build_query.build_user_prompt("Trương Định là ai?", [])
    assert "(không có)" in prompt
    assert "Trương Định là ai?" in prompt


def test_build_query_renders_history_roles() -> None:
    history = [
        ChatMessage(role="user", content="Trương Định là ai?"),
        ChatMessage(role="assistant", content="Ông là thủ lĩnh kháng Pháp."),
    ]
    prompt = build_query.build_user_prompt("Ông ấy làm gì sau đó?", history)
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
