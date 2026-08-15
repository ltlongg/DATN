"""Gom event SSE của agent-service để tái dựng assistant message lưu DB.

Thuần (không I/O) -> unit-test dễ. Vừa proxy event xuống frontend, endpoint vừa feed
từng event vào collector này; kết thúc stream thì lấy `message_fields()` để lưu (xem
backend-plan.md "SSE Persistence Strategy"). Message lưu DB khớp đúng nội dung frontend
đã thấy.
"""

from __future__ import annotations

from typing import Any

def _merge_declaration(
    previous: list[dict[str, Any]], declaration: list[Any]
) -> list[dict[str, Any]]:
    """Ráp danh sách dòng panel tiến trình MỚI lên trạng thái đã gom được.

    MERGE theo id chứ không thay thế: lượt soạn lại (B5) phát lại `steps` với danh sách dài
    hơn (thêm `synthesize:2`/`validate:2`), thay thế thì trạng thái mọi dòng đã chạy bị xoá
    sạch về "pending". Dòng chưa từng thấy khởi tạo "pending" — `state` không đi kèm danh
    sách, nó đi riêng qua event `step`.

    Trùng luật với `mergeDeclaration` trong frontend `chatReducer.ts`; lệch nhau là bản lưu
    và bản người dùng đang xem khác nhau.
    """
    by_id = {row["id"]: row for row in previous}
    merged: list[dict[str, Any]] = []
    for row in declaration:
        if not isinstance(row, dict) or not row.get("id"):
            continue
        old = by_id.get(row["id"], {})
        fresh = {**row, "state": old.get("state", "pending")}
        # `detail` và `internals` là thứ đã GOM ĐƯỢC, không phải thứ khai báo lại — bản
        # `steps` mới chỉ mang id/label/kind. Không chép sang là lượt soạn lại (B5) xoá trắng
        # tầng 2 của mọi bước đã chạy xong.
        for carried in ("detail", "internals"):
            if carried in old:
                fresh[carried] = old[carried]
        merged.append(fresh)
    return merged

class SseCollector:
    def __init__(self) -> None:
        self._tokens: list[str] = []
        # TTFT (ms) do endpoint bấm giờ và set qua mark_first_token(); collector chỉ giữ hộ để
        # message_fields() lưu kèm. None = chưa có token nào (stream lỗi/blocked sớm).
        self.ttft_ms: int | None = None
        self.citations: list[dict[str, Any]] = []
        self.visualization: dict[str, Any] | None = None
        self.clarification_needed: bool = False
        self.clarification_question: str | None = None
        self.confidence: str | None = None
        self.retrieval_mode: str = "none"
        self.warnings: list[Any] = []
        # Panel tiến trình (B3): `steps` khai báo danh sách dòng, `step` cập nhật từng dòng.
        # Gom thành MỘT mảng đã merge để reload dựng lại y hệt lúc chạy — frontend không
        # phải replay chuỗi event.
        self.steps: list[dict[str, Any]] = []
        self.blocked: bool = False
        self.error: dict[str, Any] | None = None

    @property
    def content(self) -> str:
        return "".join(self._tokens)

    def mark_first_token(self, ttft_ms: int) -> None:
        """Ghi TTFT lần ĐẦU tiên gọi, các lần sau bỏ qua. `regenerating` xoá token đã gom nhưng
        KHÔNG xoá mốc này: người dùng đã thấy chữ đầu tiên tại thời điểm đó, dù nội dung sau bị
        soạn lại."""
        if self.ttft_ms is None:
            self.ttft_ms = ttft_ms

    def feed(self, event: str, data: dict[str, Any]) -> None:
        if event == "token":
            self._tokens.append(str(data.get("text", "")))
        elif event == "citations":
            self.citations = list(data.get("citations") or [])
        elif event == "visualization":
            viz = data.get("visualization")
            self.visualization = viz if isinstance(viz, dict) else None
        elif event == "clarification":
            self.clarification_needed = True
            self.clarification_question = str(data.get("question") or "")
        elif event == "steps":
            rows = data.get("steps")
            if isinstance(rows, list):
                self.steps = _merge_declaration(self.steps, rows)
        elif event == "step":
            # id lạ -> bỏ qua, KHÔNG mọc dòng ma (cùng luật với frontend).
            for row in self.steps:
                if row.get("id") == data.get("id"):
                    row["state"] = str(data.get("state") or "pending")
                    if "detail" in data:
                        row["detail"] = data.get("detail")
                    # Collector nhận internals của MỌI lượt, kể cả người dùng thường: bản lưu
                    # phải đủ để admin soi lại hội thoại của người khác ở /admin/logs. Việc
                    # giấu khỏi người đang hỏi là của `api/chat.py`, không phải của chỗ này.
                    if "internals" in data:
                        row["internals"] = data.get("internals")
                    break
        elif event == "regenerating":
            # Agent bỏ lượt synthesize cũ, soạn lại -> xóa token đã gom để khớp frontend.
            self._tokens = []
        elif event == "blocked":
            self.blocked = True
        elif event == "error":
            self.error = {
                "code": str(data.get("code", "error")),
                "message": str(data.get("message", "")),
            }
        elif event == "done":
            self.confidence = data.get("confidence")  # có thể None
            self.retrieval_mode = str(data.get("retrieval_mode", "none"))
            self.warnings = list(data.get("warnings") or [])

    def should_persist(self) -> bool:
        """Có lưu assistant message không.

        - error -> KHÔNG lưu (frontend đã thấy lỗi qua SSE; assistant rỗng bị loại khỏi history).
        - blocked (guardrails) -> lưu safe message NẾU có content; blocked rỗng thì bỏ. Safe
          message lưu như assistant message thường để còn thấy khi reload (event `blocked` chỉ
          là trạng thái realtime, không tồn tại sau reload — xem guardrails-input-plan.md).
        - clarification -> lưu (cần trong history cho lượt sau).
        - câu trả lời thường -> lưu nếu có nội dung.
        """
        if self.error is not None:
            return False
        if self.clarification_needed:
            return True
        return bool(self.content.strip())

    def _closed_steps(self) -> list[dict[str, Any]]:
        """Bản `steps` để LƯU: stream đã đóng nên dòng còn `running` là dòng không bao giờ
        có kết (lỗi/abort giữa chừng) -> hạ xuống `partial`, đúng luật frontend áp lúc stream
        đóng (plan §7.3.1 mục 5). Không hạ thì reload ra spinner quay mãi.

        Trả list MỚI, không sửa `self.steps`, để gọi nhiều lần vẫn ra cùng kết quả.
        """
        return [
            {**row, "state": "partial"} if row.get("state") == "running" else row
            for row in self.steps
        ]

    def message_fields(self) -> dict[str, Any]:
        """kwargs cho models.conversation.add_message (chỉ gọi khi should_persist())."""
        if self.clarification_needed:
            return {
                "role": "assistant",
                "content": self.clarification_question or "",
                "clarification_needed": True,
                "retrieval_mode": "none",
                "steps": self._closed_steps(),
                "ttft_ms": self.ttft_ms,
            }
        return {
            "role": "assistant",
            "content": self.content,
            "clarification_needed": False,
            "citations": self.citations,
            "visualization": self.visualization,
            "retrieval_mode": self.retrieval_mode,
            "confidence": self.confidence,
            "warnings": self.warnings,
            "steps": self._closed_steps(),
            "ttft_ms": self.ttft_ms,
        }
