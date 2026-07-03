# Guardrails Input Layer Plan

## Summary
- Xây guardrails v1 với 1 lớp kiểm tra input trước `build_query`.
- Chỉ dùng LLM structured output, không dùng regex, keyword, hay blocklist.
- Guardrails dùng model riêng nhỏ/rẻ qua `GUARDRAILS_LLM_MODEL`, mặc định `gpt-4o-mini`.
- Khi input bị chặn, agent-service stream một safe message qua SSE `token`, sau đó emit `blocked` để frontend biết trạng thái realtime.
- Backend lưu safe assistant message như message thường; không thêm field DB mới trong v1.

## Key Changes
- Thêm config agent-service:
  - `guardrails_enabled: bool = True`
  - `guardrails_llm_model: str = "gpt-4o-mini"`
  - `guardrails_timeout_seconds: int = 8`
  - `guardrails_fail_closed: bool = True`
- Thêm `.env.example`:
  - `GUARDRAILS_LLM_MODEL=gpt-4o-mini`
- Implement `check_input(question, history) -> GuardrailDecision` trong `app/orchestrator/guardrails.py`.
- Guardrails gọi trực tiếp `settings.guardrails_llm_model`, không fallback sang `orchestrator_llm_model` hoặc `llm_model`.
- Thêm node `guard_input` trước `build_query`.
- Nếu `allow`, flow chạy như hiện tại.
- Nếu `block`, emit:
  ```text
  event: token
  data: {"text":"<safe_message>"}

  event: blocked
  data: {"stage":"input","categories":["..."]}
  ```
- Sau khi block, không gọi `build_query`, retrieval, hoặc synthesize.
- Backend collector persist safe assistant message nếu có content, kể cả khi đã thấy event `blocked`.
- Frontend hiển thị safe message từ token; `blocked` chỉ dùng cho trạng thái realtime trong lượt stream hiện tại.

## Policy Defaults
- Cho phép câu hỏi lịch sử Việt Nam nhạy cảm nếu mục đích học thuật/giáo dục.
- Chặn prompt injection/jailbreak, yêu cầu lộ hidden instructions, hướng dẫn gây hại, tự hại, hoạt động phi pháp, nội dung tình dục không phù hợp, thù ghét/quấy rối, và yêu cầu lộ secret/dữ liệu riêng tư.
- Nếu guardrails model lỗi hoặc timeout, với `guardrails_fail_closed=true`, emit safe message mặc định rồi emit `blocked`.

## Test Plan
- Agent-service:
  - Input allow đi tiếp qua `build_query`.
  - Input block emit `token(safe_message)` rồi `blocked`.
  - Input block không gọi `build_query`, retrieval, synthesize, và không emit `done`.
  - Timeout/model error vẫn trả safe message khi `fail_closed=true`.
  - Usage log ghi `task="guardrail_input"` và đúng `guardrails_llm_model`.
  - Module guardrails không import/use `re`, không có keyword/blocklist classifier.
- Backend:
  - Proxy đúng thứ tự `token` rồi `blocked`.
  - Collector gom safe message và vẫn persist khi blocked có content.
  - Reload conversation thấy lại safe assistant message.
- Frontend:
  - SSE parser xử lý `token` trước `blocked`.
  - Reducer giữ `content` là safe message và set `blocked=true`.
  - Message bubble hiển thị safe message; không thay bằng câu cố định nếu content đã có.

## Assumptions
- Scope v1 chỉ là input guardrails runtime.
- Chưa làm output batch guardrails, dashboard incident, admin config, hoặc DB metadata cho blocked messages.
- Event `blocked` chỉ là trạng thái realtime, không cần tồn tại sau khi reload conversation.
- Model mặc định là `gpt-4o-mini`, có thể đổi qua `.env`.
- Mọi quyết định allow/block đều do LLM structured output.
