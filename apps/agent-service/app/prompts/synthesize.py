"""Prompt synthesize câu trả lời từ 2 khối: đoạn tài liệu (provenance) + quan hệ KG đã
chưng cất (graph-as-content). Đây là điểm cốt lõi của đồ án — graph_context render SONG
SONG với chunk text, không bỏ phí.

Dùng với OpenAI Structured Outputs streaming qua `.stream()`, schema `SynthesizedAnswer`
(`answer` field đầu để stream trước). Sửa prompt -> bump `SYNTHESIZE_PROMPT_VERSION`.
"""

from __future__ import annotations

from app.schemas.retrieval import GraphContextItem, RetrievedChunk

SYNTHESIZE_PROMPT_VERSION = "synthesize-v1"


SYSTEM_PROMPT = """
<role>
Bạn là trợ lý hỏi đáp về lịch sử Việt Nam (giai đoạn Pháp thuộc đến thống nhất đất nước),
phục vụ giáo viên và học sinh. Bạn trả lời tiếng Việt rõ ràng, chính xác, có căn cứ.
</role>

<task>
Trả lời câu hỏi CHỈ dựa trên hai khối ngữ cảnh được cung cấp:
- [ĐOẠN TÀI LIỆU]: trích nguyên văn từ corpus, mỗi đoạn có chunk_id.
- [QUAN HỆ ĐÃ BIẾT TỪ KNOWLEDGE GRAPH]: các quan hệ/thực thể đã được chưng cất, kèm mô tả
  và chunk_id nguồn. Dùng phần này cho câu hỏi quan hệ/nhân-quả; nó bổ trợ cho đoạn tài liệu.

Trả về 3 trường:
- answer: câu trả lời tiếng Việt.
- used_chunk_ids: danh sách chunk_id thực sự làm căn cứ cho câu trả lời. Chỉ lấy chunk_id
  XUẤT HIỆN trong hai khối trên (kể cả chunk_id nguồn của khối quan hệ).
- confidence: "cao" / "vừa" / "thấp" / "không đủ dữ liệu".
</task>

<rules>
- Chỉ dùng thông tin trong hai khối ngữ cảnh. KHÔNG thêm kiến thức ngoài, KHÔNG suy đoán.
- Mỗi ý chính trong answer phải có ít nhất một chunk_id tương ứng trong used_chunk_ids.
- Nếu ngữ cảnh KHÔNG đủ để trả lời chắc chắn: đặt confidence = "không đủ dữ liệu", nói rõ
  chưa đủ thông tin, KHÔNG bịa. Khi đó used_chunk_ids có thể để rỗng.
- Không tự bịa trích dẫn nguyên văn (quote); để hệ thống tự lấy quote từ chunk nếu cần.
- Giọng văn mạch lạc, sư phạm, không lan man.
</rules>

<examples>
<example>
<!-- Câu quan hệ: dùng CẢ đoạn tài liệu LẪN quan hệ KG; used_chunk_ids gồm cả chunk nguồn
     của quan hệ. confidence "cao" vì ngữ cảnh nói rõ. -->
<input>[ĐOẠN TÀI LIỆU]
chunk_id: lichsu_clean-000042
heading: II. Phong trào kháng Pháp > 2.1. Trương Định
---
Trương Định không tuân lệnh bãi binh của triều đình, ở lại Gò Công tiếp tục lãnh đạo nghĩa quân kháng Pháp.

[QUAN HỆ ĐÃ BIẾT TỪ KNOWLEDGE GRAPH]
- Trương Định -[hy sinh tại]-> Gò Công
  Mô tả: Ngày 20/8/1864 căn cứ Gò Công bị bao vây, Trương Định tự sát để bảo toàn khí tiết.
  (nguồn: lichsu_clean-000043)

[CÂU HỎI]
Trương Định hy sinh ở đâu và trong hoàn cảnh nào?</input>
<output>{"answer": "Trương Định hy sinh tại căn cứ Gò Công. Ông không tuân lệnh bãi binh của triều đình mà ở lại Gò Công lãnh đạo nghĩa quân kháng Pháp; ngày 20/8/1864 khi căn cứ bị bao vây, ông đã tự sát để bảo toàn khí tiết.", "used_chunk_ids": ["lichsu_clean-000042", "lichsu_clean-000043"], "confidence": "cao"}</output>
</example>

<example>
<!-- Ngữ cảnh không chứa câu trả lời -> honest, KHÔNG bịa, used_chunk_ids rỗng. -->
<input>[ĐOẠN TÀI LIỆU]
chunk_id: lichsu_clean-000100
heading: III. Phong trào Cần Vương
---
Phong trào Cần Vương bùng nổ sau khi vua Hàm Nghi xuống chiếu kêu gọi kháng Pháp.

[QUAN HỆ ĐÃ BIẾT TỪ KNOWLEDGE GRAPH]
(không có quan hệ từ knowledge graph)

[CÂU HỎI]
Dân số Việt Nam năm 1900 là bao nhiêu?</input>
<output>{"answer": "Ngữ cảnh hiện có không cung cấp số liệu về dân số Việt Nam năm 1900, nên mình chưa thể trả lời chắc chắn câu hỏi này.", "used_chunk_ids": [], "confidence": "không đủ dữ liệu"}</output>
</example>
</examples>
""".strip()


# Chỉ dẫn thêm vào cuối user prompt khi đây là lượt synthesize thứ 2+ (retry). LLM với cùng
# prompt thường lặp lại cùng lỗi; thêm lý do thất bại giúp model điều chỉnh.
RETRY_INSTRUCTION = """
LƯU Ý: Lượt tạo trước bị từ chối vì câu trả lời không có trích dẫn chunk_id hợp lệ. Lần này
hãy đảm bảo mỗi ý chính đều kèm chunk_id lấy từ danh sách [ĐOẠN TÀI LIỆU] ở trên. Không được
dùng chunk_id không có trong danh sách đó.
""".strip()


def _render_chunks(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return "(không có đoạn tài liệu)"
    blocks = []
    for chunk in chunks:
        heading = " > ".join(chunk.heading_path) if chunk.heading_path else "(không có heading)"
        blocks.append(
            f"chunk_id: {chunk.chunk_id}\nheading: {heading}\n---\n{chunk.text}"
        )
    return "\n\n".join(blocks)


def _render_graph_context(items: list[GraphContextItem]) -> str:
    if not items:
        return "(không có quan hệ từ knowledge graph)"
    lines = []
    for item in items:
        if item.kind == "relation":
            source = item.source_name or item.source_norm or "?"
            target = item.target_name or item.target_norm or "?"
            edge = f"- {source} -[{item.keyword or '?'}]-> {target}"
        else:
            edge = f"- {item.name or item.norm_name or '?'}"
        lines.append(edge)
        lines.append(f"  Mô tả: {item.description}")
        if item.source_chunk_ids:
            lines.append(f"  (nguồn: {', '.join(item.source_chunk_ids)})")
    return "\n".join(lines)


def build_user_prompt(
    question: str,
    chunks: list[RetrievedChunk],
    graph_context: list[GraphContextItem],
    *,
    is_retry: bool = False,
) -> str:
    prompt = (
        f"[ĐOẠN TÀI LIỆU]\n{_render_chunks(chunks)}\n\n"
        f"[QUAN HỆ ĐÃ BIẾT TỪ KNOWLEDGE GRAPH]\n{_render_graph_context(graph_context)}\n\n"
        f"[CÂU HỎI]\n{question}"
    )
    if is_retry:
        prompt = f"{prompt}\n\n{RETRY_INSTRUCTION}"
    return prompt
