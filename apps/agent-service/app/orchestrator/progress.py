"""Panel tiến trình (B3) — dựng danh sách bước + dòng phụ cho NGƯỜI DÙNG.

Thuần: không I/O, không LLM. Đây là ràng buộc thiết kế của plan §7.3 mục 2 — dòng phụ do
CODE ghép từ số liệu đã có sẵn (mode, số query, số chunk, confidence), **tuyệt đối không
thêm LLM call "người dẫn chuyện"**: template chuỗi thì không bịa được, LLM thì có.

**Hai tầng chi tiết trên CÙNG một danh sách bước** (đổi 2026-08-01). Trước đây panel tiến
trình (người dùng) và DebugPanel (admin) là hai khối rời, vẽ cùng một chuỗi bước bằng hai
nguồn khác nhau — và vẽ LỆCH nhau: panel đọc `steps`, DebugPanel đọc event `status`, nên câu
xã giao hiện "1/1 bước" ở trên còn "plan + direct_response" ở dưới. DebugPanel đã bị xoá;
số liệu thô của nó giờ là `internals` gắn vào ĐÚNG bước sinh ra nó, mở ra khi admin bấm.

Kèm theo: `internals` đi ngay trong event `step` lúc bước chạy, KHÔNG gom một lần sát `done`
như event `debug` cũ — chính cách gom muộn đó đẻ ra mấy dòng "Đang xử lý…" kẹt vĩnh viễn ở
những nhánh không bao giờ chạy tới (smalltalk, out_of_scope).

Ai thấy `internals` là do BACKEND quyết (`api/chat.py` bóc ra khi `debug=False`), không phải
agent — agent luôn gửi để bản lưu vào `messages.steps` đủ cho admin soi lại về sau.

Event `status` (`nodes.py`, `{"node","msg"}`) GIỮ NGUYÊN nhưng frontend hết đọc: nó còn ích
khi test bằng curl/Swagger, và `debug` state vẫn là payload của `/ask` non-stream.

**Phạm vi hiện tại** — B4 (multi-step) đã bỏ nên danh sách là `1 + N + 2`: `plan` -> N bước
todo -> `synthesize:1` -> `validate:1`. Chưa có dòng `resolve` (B4); state `skipped` của
plan §7.3 mục 1 cũng chưa dựng vì nó chỉ xảy ra khi list bị dừng sớm giữa chừng (B4). Thêm
khi tới lượt, không dựng sẵn chỗ trống.

Lượt soạn lại (B5) **mọc thêm dòng mới** `synthesize:2`/`validate:2` chứ KHÔNG ghi đè dòng
cũ (plan §7.3.1 mục 1): người dùng phải thấy được là hệ thống đã soạn lại, đó chính là điều
đáng nói. Kéo theo: `steps` được phát LẠI với danh sách dài hơn, nên cả frontend lẫn
`SseCollector` đều phải MERGE theo id thay vì thay thế.
"""

from __future__ import annotations

from typing import Any, Literal

from app.schemas.ask import AnswerConfidence, PlanStep, RouteDecision
from app.schemas.retrieval import RetrievalMode

# State agent PHÁT ra. Frontend còn một state thứ tư `pending` cho dòng đã khai báo trong
# `steps` nhưng chưa chạy tới — nó thuần hiển thị, agent không bao giờ emit.
StepState = Literal["running", "done", "partial"]

# Tầng 2 của panel: bảng nhãn/giá trị hiện khi admin mở rộng MỘT bước (thay cho DebugPanel
# cũ). Value luôn là chuỗi đã format sẵn — frontend render generic, không switch theo bước;
# thêm bước mới không phải sửa React.
InternalRow = dict[str, str]

PLAN_STEP_ID = "plan"
VISUALIZATION_STEP_ID = "visualization"

PLAN_STEP_LABEL = "Phân tích câu hỏi"
SYNTHESIZE_STEP_LABEL = "Soạn câu trả lời"
VALIDATE_STEP_LABEL = "Đối chiếu trích dẫn với nguồn"
VISUALIZATION_STEP_LABEL = "Dựng bản đồ & dòng thời gian"

# Confidence khiến bước soạn bài về `partial` thay vì `done` (plan §7.3 mục 1): trả lời
# xong nhưng chính hệ thống không chắc -> không được cho tick xanh.
_WEAK_CONFIDENCE: frozenset[str] = frozenset({"thấp", "không đủ dữ liệu"})

# Nguồn thật sự chạy ở mỗi mode — nói đúng cái đã làm, không nói chung chung "đang tìm".
_MODE_SOURCES: dict[RetrievalMode, str] = {
    "hybrid": "Dense + BM25 + graph",
    "traditional": "Dense + BM25",
    "graph": "Knowledge graph",
}

# Route không cần truy hồi -> danh sách chỉ có đúng dòng `plan`, và dòng đó tự giải thích
# vì sao dừng ở đây.
_NON_RETRIEVAL_DETAIL: dict[RouteDecision, str] = {
    "ambiguous": "Câu hỏi chưa rõ · cần hỏi lại",
    "smalltalk": "Câu xã giao · không cần tra tài liệu",
    "out_of_scope": "Ngoài phạm vi tài liệu",
}


def todo_step_id(step_id: int) -> str:
    return f"todo:{step_id}"


def synthesize_step_id(attempt: int) -> str:
    """`attempt` đếm từ 1. Lượt soạn lại ra id KHÁC để dòng cũ còn nguyên trên panel."""
    return f"synthesize:{attempt}"


def validate_step_id(attempt: int) -> str:
    return f"validate:{attempt}"


def build_step_list(
    route: RouteDecision, steps: list[PlanStep], *, attempts: int = 1
) -> list[dict[str, str]]:
    """Danh sách dòng sẽ hiện, theo đúng thứ tự luồng chạy.

    Chỉ khai báo id/label/kind — KHÔNG kèm state: state đi riêng qua event `step` để một
    dòng cập nhật được nhiều lần (running -> done) mà không phải gửi lại cả danh sách.

    `attempts` = số lượt soạn bài đã/đang chạy. Gọi lại với số lớn hơn khi retry để danh
    sách dài ra; bên nhận merge theo id nên các dòng cũ giữ nguyên trạng thái.
    """
    rows = [{"id": PLAN_STEP_ID, "label": PLAN_STEP_LABEL, "kind": "system"}]
    if route != "needs_retrieval":
        return rows
    rows.extend(
        {"id": todo_step_id(s.id), "label": s.label, "kind": "retrieve"} for s in steps
    )
    for attempt in range(1, attempts + 1):
        rows.append(
            {
                "id": synthesize_step_id(attempt),
                "label": SYNTHESIZE_STEP_LABEL,
                "kind": "system",
            }
        )
        rows.append(
            {
                "id": validate_step_id(attempt),
                "label": VALIDATE_STEP_LABEL,
                "kind": "system",
            }
        )
    # LUÔN cuối danh sách, kể cả khi retry đẩy thêm cặp synthesize/validate vào giữa.
    # Nhánh honest_answer không đi qua node này -> dòng ở lại `pending` ("không chạy"),
    # đúng nghĩa chứ không phải lỗi.
    rows.append(
        {
            "id": VISUALIZATION_STEP_ID,
            "label": VISUALIZATION_STEP_LABEL,
            "kind": "system",
        }
    )
    return rows


def plan_detail(route: RouteDecision, steps: list[PlanStep]) -> str:
    """Dòng phụ của bước `plan`.

    Bậc B1 luôn đúng 1 bước (`nodes.MAX_STEPS`), nên cái ĐÁNG kể ở đây là số truy vấn tách
    ra chạy song song, không phải số bước. Nhánh "N bước phụ thuộc nhau" thuộc về B4 — chưa
    viết vì hiện không có đường nào chạy tới.
    """
    if route != "needs_retrieval":
        return _NON_RETRIEVAL_DETAIL[route]
    query_count = sum(len(s.queries) for s in steps)
    if query_count > 1:
        return f"Tách {query_count} truy vấn · tìm song song"
    return "Câu hỏi đơn · 1 bước"


def retrieve_detail(mode: RetrievalMode, *, query_count: int, chunk_count: int) -> str:
    if chunk_count == 0:
        return "Không tìm thấy đoạn phù hợp"
    parts = [_MODE_SOURCES[mode]]
    if query_count > 1:
        parts.append(f"{query_count} truy vấn song song")
    parts.append(f"{chunk_count} đoạn")
    return " · ".join(parts)


def retrieve_state(chunk_count: int) -> StepState:
    return "done" if chunk_count > 0 else "partial"


def synthesize_detail(*, context_count: int, confidence: AnswerConfidence | None) -> str:
    base = f"Soạn từ {context_count} đoạn"
    return f"{base} · độ tin cậy {confidence}" if confidence else base


def synthesize_state(confidence: AnswerConfidence | None) -> StepState:
    return "partial" if confidence in _WEAK_CONFIDENCE else "done"


def validate_detail(*, valid: int, total: int, will_retry: bool) -> str:
    """Chữ phải khớp ĐÚNG việc node làm (plan §6 + §7.3 mục 2).

    Nói "khớp nguồn đã truy hồi", KHÔNG nói "đã xác minh": node chỉ kiểm `chunk_id` có thuộc
    tập vừa truy hồi hay không, không hề đối chiếu câu văn với nội dung đoạn. Chữ "xác minh"
    ở đây làm người đọc tin hơn mức đáng tin — đúng thứ domain lịch sử không cho phép.

    "soạn lại" chỉ được xuất hiện khi hệ thống THẬT SỰ soạn lại. `after_validate` chỉ retry ở
    ca 0 liên kết hợp lệ, nên 3/5 sai vẫn đi tiếp — viết "soạn lại" ở đó là mô tả sai luồng.
    """
    base = (
        "Không có liên kết nguồn nào"
        if total == 0
        else f"{valid}/{total} liên kết nguồn hợp lệ"
    )
    return f"{base} · soạn lại" if will_retry else base


def validate_state(valid: int) -> StepState:
    return "done" if valid > 0 else "partial"


# --- visualization ---


def visualization_detail(
    *, event_count: int, marker_count: int, timeline_count: int, unplaced: int
) -> str:
    """Đặt số MỐC trước số MARKER có chủ đích: gazetteer đang hoãn (xem CLAUDE.md) nên
    marker gần như luôn 0. Dẫn bằng con số 0 đó thì dòng phụ đọc như hệ thống hỏng, trong
    khi timeline vẫn dựng đủ."""
    if event_count == 0:
        return "Không có sự kiện nào gắn với nguồn đã dùng"
    parts = [f"{timeline_count} mốc thời gian"]
    if marker_count > 0:
        parts.append(f"{marker_count} điểm trên bản đồ")
    if unplaced > 0:
        parts.append(f"{unplaced} thiếu dữ liệu hiển thị")
    return " · ".join(parts)


def visualization_state(event_count: int) -> StepState:
    return "done" if event_count > 0 else "partial"


# --- internals (tầng 2, chỉ admin thấy — xem docstring module) ---


def _row(label: str, value: object) -> InternalRow:
    return {"label": label, "value": str(value)}


def plan_internals(
    *, standalone_query: str, route: str, selected_mode: str, mode_source: str
) -> list[InternalRow]:
    source = "người dùng ép" if mode_source == "override" else "agent chọn"
    return [
        _row("Câu viết lại", standalone_query),
        _row("Định tuyến", route),
        _row("Cách truy hồi", f"{selected_mode} ({source})"),
    ]


def retrieve_internals(
    queries: list[dict[str, Any]], *, total_chunks: int, graph_context: int
) -> list[InternalRow]:
    """`queries` là ĐÚNG list đã dựng cho `debug.retrieve` (query/entities/chunks).

    Ghép câu truy vấn với số đoạn nó trả về trong CÙNG một dòng — DebugPanel cũ để hai thứ
    này ở hai mục rời nhau, phải tự nhẩm mới biết truy vấn nào tách ra vô ích.
    """
    rows: list[InternalRow] = []
    for i, q in enumerate(queries, start=1):
        text = str(q.get("query", ""))
        entities = q.get("entities") or []
        if entities:
            text = f"{text}  ·  seed: {', '.join(str(e) for e in entities)}"
        rows.append(_row(f"Truy vấn {i}", f"{text}  →  {q.get('chunks', 0)} đoạn"))
    rows.append(_row("Tổng đã gộp", f"{total_chunks} đoạn"))
    rows.append(_row("Ngữ cảnh graph", f"{graph_context} quan hệ"))
    return rows


def synthesize_internals(
    *, prompt_chunks: int, citation_only_chunks: int, model: str, attempt: int
) -> list[InternalRow]:
    """`citation_only_chunks` chưa từng hiện ở đâu: chunk provenance-only bị loại khỏi prompt
    nhưng vẫn nằm trong tập trích dẫn được. Chênh lệch giữa hai con số này là thứ giải thích
    vì sao "truy hồi 12 đoạn" mà "soạn từ 9 đoạn" — không có nó thì trông như mất đoạn."""
    rows = [
        _row("Đoạn đưa vào prompt", prompt_chunks),
        _row("Model", model),
    ]
    if citation_only_chunks > 0:
        rows.insert(1, _row("Đoạn chỉ để trích dẫn", citation_only_chunks))
    if attempt > 1:
        rows.append(_row("Lượt soạn", f"lần {attempt}"))
    return rows


def validate_internals(
    *, claimed: int, valid: int, dropped: list[str], will_retry: bool
) -> list[InternalRow]:
    """`dropped` = id LLM nêu mà không có trong tập vừa truy hồi — dấu hiệu bịa trích dẫn,
    và là lý do chính đáng nhất để giữ tầng 2 này lại sau khi bỏ DebugPanel."""
    rows = [
        _row("LLM khai", f"{claimed} nguồn"),
        _row("Hợp lệ", f"{valid} nguồn"),
        _row("Bị loại", ", ".join(dropped) if dropped else "—"),
    ]
    if will_retry:
        rows.append(_row("Hành động", "soạn lại"))
    return rows


def visualization_internals(
    *, event_count: int, marker_count: int, timeline_count: int, unplaced: int
) -> list[InternalRow]:
    return [
        _row("Sự kiện khớp nguồn", event_count),
        _row("Mốc thời gian", timeline_count),
        _row("Marker bản đồ", marker_count),
        _row("Thiếu dữ liệu hiển thị", unplaced),
    ]
