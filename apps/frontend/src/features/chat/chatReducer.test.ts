import { describe, it, expect } from "vitest";
import { chatReducer, type ChatItem } from "@/features/chat/chatReducer";

/** Dựng state có 1 bong bóng assistant đang stream với id cho trước. */
function startState(assistantId: string, at = 1_000): ChatItem[] {
  return chatReducer([], {
    type: "startTurn",
    userId: "u1",
    userText: "câu hỏi",
    assistantId,
    at,
  });
}

describe("chatReducer — guardrails blocked", () => {
  it("giữ safe message ở content và set blocked=true khi token rồi blocked", () => {
    const id = "a1";
    let state = startState(id);
    // Agent stream safe message qua token TRƯỚC, rồi blocked.
    state = chatReducer(state, { type: "token", id, text: "Xin lỗi, mình không hỗ trợ " });
    state = chatReducer(state, { type: "token", id, text: "yêu cầu này." });
    state = chatReducer(state, { type: "blocked", id });

    const assistant = state.find((it) => it.id === id)!;
    expect(assistant.blocked).toBe(true);
    // Content KHÔNG bị thay bằng câu cố định — vẫn là safe message đã stream.
    expect(assistant.content).toBe("Xin lỗi, mình không hỗ trợ yêu cầu này.");
    // Blocked kết thúc lượt (agent không gửi done) -> streaming tắt để bỏ con trỏ nhấp nháy.
    expect(assistant.streaming).toBe(false);
  });

  it("blocked không có content vẫn set cờ blocked (bong bóng rơi về câu cố định ở UI)", () => {
    const id = "a2";
    let state = startState(id);
    state = chatReducer(state, { type: "blocked", id });

    const assistant = state.find((it) => it.id === id)!;
    expect(assistant.blocked).toBe(true);
    expect(assistant.content).toBe("");
    expect(assistant.streaming).toBe(false);
  });
});

describe("chatReducer — panel tiến trình (B3)", () => {
  const DECL = [
    { id: "plan", label: "Phân tích câu hỏi", kind: "system" as const },
    { id: "todo:1", label: "Tìm Trương Định", kind: "retrieve" as const },
    { id: "synthesize:1", label: "Soạn câu trả lời", kind: "system" as const },
  ];

  it("mở lượt là đã có sẵn dòng plan đang chạy, không đợi agent", () => {
    const assistant = startState("a1", 5_000).find((it) => it.id === "a1")!;
    expect(assistant.steps).toEqual([
      { id: "plan", label: "Phân tích câu hỏi", kind: "system", state: "running" },
    ]);
    expect(assistant.startedAt).toBe(5_000);
  });

  it("danh sách từ agent KHÔNG đạp ngược dòng plan đang chạy về pending", () => {
    const id = "a1";
    let state = startState(id);
    state = chatReducer(state, { type: "steps", id, steps: DECL });
    const steps = state.find((it) => it.id === id)!.steps;
    expect(steps.map((s) => s.id)).toEqual(["plan", "todo:1", "synthesize:1"]);
    expect(steps[0].state).toBe("running"); // giữ nguyên, không nháy
    expect(steps[1].state).toBe("pending");
  });

  it("cập nhật từng dòng theo id, kèm dòng phụ", () => {
    const id = "a1";
    let state = startState(id);
    state = chatReducer(state, { type: "steps", id, steps: DECL });
    state = chatReducer(state, {
      type: "step",
      id,
      step: { id: "todo:1", state: "done", detail: "Dense + BM25 + graph · 8 đoạn" },
    });
    const todo = state.find((it) => it.id === id)!.steps[1];
    expect(todo.state).toBe("done");
    expect(todo.detail).toBe("Dense + BM25 + graph · 8 đoạn");
  });

  it("cập nhật không kèm detail thì giữ nguyên dòng phụ cũ", () => {
    const id = "a1";
    let state = startState(id);
    state = chatReducer(state, { type: "steps", id, steps: DECL });
    state = chatReducer(state, {
      type: "step",
      id,
      step: { id: "todo:1", state: "done", detail: "8 đoạn" },
    });
    state = chatReducer(state, { type: "step", id, step: { id: "todo:1", state: "partial" } });
    const todo = state.find((it) => it.id === id)!.steps[1];
    expect(todo.state).toBe("partial");
    expect(todo.detail).toBe("8 đoạn");
  });

  it("bỏ qua step có id không nằm trong danh sách (không mọc dòng ma)", () => {
    const id = "a1";
    let state = startState(id);
    state = chatReducer(state, { type: "steps", id, steps: DECL });
    state = chatReducer(state, { type: "step", id, step: { id: "todo:9", state: "done" } });
    expect(state.find((it) => it.id === id)!.steps).toHaveLength(3);
  });

  it("done hạ mọi dòng còn running xuống partial, giữ nguyên pending", () => {
    const id = "a1";
    let state = startState(id);
    state = chatReducer(state, { type: "steps", id, steps: DECL });
    state = chatReducer(state, { type: "step", id, step: { id: "plan", state: "done" } });
    state = chatReducer(state, { type: "step", id, step: { id: "todo:1", state: "running" } });
    state = chatReducer(state, {
      type: "done",
      id,
      done: {
        confidence: "cao",
        retrieval_mode: "hybrid",
        warnings: [],
        conversation_id: "c1",
        message_id: "m1",
        ttft_ms: 900,
      },
    });
    const steps = state.find((it) => it.id === id)!.steps;
    expect(steps.map((s) => s.state)).toEqual(["done", "partial", "pending"]);
  });

  it("giữ nguyên dòng skipped khi stream đóng — 'bị bỏ' không phải 'chạy dở'", () => {
    // Todo list dừng sớm (B4): bước sau bị agent đánh dấu `skipped`. Hạ nó xuống `partial`
    // như dòng `running` là nói dối rằng bước đó có chạy.
    const id = "a1";
    let state = startState(id);
    state = chatReducer(state, { type: "steps", id, steps: DECL });
    state = chatReducer(state, { type: "step", id, step: { id: "plan", state: "done" } });
    state = chatReducer(state, { type: "step", id, step: { id: "todo:1", state: "skipped" } });
    state = chatReducer(state, {
      type: "done",
      id,
      done: {
        confidence: "vừa",
        retrieval_mode: "hybrid",
        warnings: [],
        conversation_id: "c1",
        message_id: "m1",
        ttft_ms: 900,
      },
    });
    const steps = state.find((it) => it.id === id)!.steps;
    expect(steps.map((s) => s.state)).toEqual(["done", "skipped", "pending"]);
  });

  it("lỗi giữa chừng cũng kết dòng lại và tắt streaming", () => {
    const id = "a1";
    let state = startState(id);
    state = chatReducer(state, { type: "steps", id, steps: DECL });
    state = chatReducer(state, { type: "step", id, step: { id: "plan", state: "done" } });
    state = chatReducer(state, { type: "step", id, step: { id: "todo:1", state: "running" } });
    state = chatReducer(state, {
      type: "error",
      id,
      error: { code: "all_backends_failed", message: "hỏng" },
    });
    const assistant = state.find((it) => it.id === id)!;
    expect(assistant.streaming).toBe(false);
    // Bước tìm dừng dở -> partial; bước soạn bài chưa từng chạy -> pending, KHÔNG partial.
    expect(assistant.steps.map((s) => s.state)).toEqual(["done", "partial", "pending"]);
  });

  it("nạp hội thoại cũ dựng lại panel từ messages.steps, nhưng không có mốc thời gian", () => {
    const state = chatReducer([], {
      type: "load",
      messages: [
        {
          id: "m1",
          role: "assistant",
          content: "Đáp án.",
          clarification_needed: false,
          citations: [],
          visualization: null,
          retrieval_mode: "hybrid",
          confidence: "cao",
          warnings: [],
          steps: [
            { id: "plan", label: "Phân tích câu hỏi", kind: "system", state: "done" },
          ],
          ttft_ms: 800,
          created_at: "2026-07-31T00:00:00Z",
        },
      ],
    });
    expect(state[0].steps).toHaveLength(1);
    expect(state[0].startedAt).toBeNull();
  });
});

describe("chatReducer — lượt soạn lại (B5)", () => {
  const DECL_1 = [
    { id: "plan", label: "Phân tích câu hỏi", kind: "system" as const },
    { id: "synthesize:1", label: "Soạn câu trả lời", kind: "system" as const },
    { id: "validate:1", label: "Đối chiếu trích dẫn với nguồn", kind: "system" as const },
  ];
  const DECL_2 = [
    ...DECL_1,
    { id: "synthesize:2", label: "Soạn câu trả lời", kind: "system" as const },
    { id: "validate:2", label: "Đối chiếu trích dẫn với nguồn", kind: "system" as const },
  ];

  it("danh sách phát lại dài hơn thì nối thêm dòng, không xoá trạng thái dòng cũ", () => {
    const id = "a1";
    let state = startState(id);
    state = chatReducer(state, { type: "steps", id, steps: DECL_1 });
    state = chatReducer(state, { type: "step", id, step: { id: "plan", state: "done" } });
    state = chatReducer(state, {
      type: "step",
      id,
      step: { id: "validate:1", state: "partial", detail: "0/1 liên kết nguồn hợp lệ · soạn lại" },
    });
    state = chatReducer(state, { type: "steps", id, steps: DECL_2 });

    const steps = state.find((it) => it.id === id)!.steps;
    expect(steps.map((s) => s.id)).toEqual([
      "plan",
      "synthesize:1",
      "validate:1",
      "synthesize:2",
      "validate:2",
    ]);
    expect(steps[0].state).toBe("done");
    expect(steps[2].detail).toBe("0/1 liên kết nguồn hợp lệ · soạn lại");
    expect(steps[3].state).toBe("pending");
  });

  it("regenerating xoá chữ lượt cũ nhưng KHÔNG xoá dòng nào trên panel", () => {
    const id = "a1";
    let state = startState(id);
    state = chatReducer(state, { type: "steps", id, steps: DECL_1 });
    state = chatReducer(state, { type: "token", id, text: "câu trả lời hỏng" });
    state = chatReducer(state, { type: "regenerating", id });

    const assistant = state.find((it) => it.id === id)!;
    expect(assistant.content).toBe("");
    expect(assistant.steps).toHaveLength(3); // lịch sử bước còn nguyên
  });

  it("danh sách phát lại KHÔNG xoá internals của dòng đã xong", () => {
    // Cùng lý do với `detail`: bản `steps` mới chỉ mang id/label/kind. Bỏ qua là admin mất
    // sạch tầng 2 của mọi bước đã chạy ngay khi hệ thống soạn lại.
    const id = "a1";
    let state = startState(id);
    state = chatReducer(state, { type: "steps", id, steps: DECL_1 });
    state = chatReducer(state, {
      type: "step",
      id,
      step: { id: "plan", state: "done", internals: [{ label: "Model", value: "m" }] },
    });
    state = chatReducer(state, { type: "steps", id, steps: DECL_2 });

    const steps = state.find((it) => it.id === id)!.steps;
    expect(steps[0].internals).toEqual([{ label: "Model", value: "m" }]);
    expect(steps[3].internals).toBeUndefined(); // dòng mới, chưa chạy
  });
});

describe("chatReducer — internals (tầng 2 panel tiến trình)", () => {
  const DECL = [{ id: "plan", label: "Phân tích câu hỏi", kind: "system" as const }];

  it("step mang internals thì gắn vào đúng dòng", () => {
    const id = "a1";
    let state = startState(id);
    state = chatReducer(state, { type: "steps", id, steps: DECL });
    state = chatReducer(state, {
      type: "step",
      id,
      step: {
        id: "plan",
        state: "done",
        internals: [{ label: "Định tuyến", value: "smalltalk" }],
      },
    });
    expect(state.find((it) => it.id === id)!.steps[0].internals).toEqual([
      { label: "Định tuyến", value: "smalltalk" },
    ]);
  });

  it("step KHÔNG mang internals thì giữ nguyên cái cũ, không xoá", () => {
    // Người dùng thường không bao giờ nhận field này (backend bóc) -> "vắng mặt" phải đọc là
    // "không có gì mới", không phải "xoá đi".
    const id = "a1";
    let state = startState(id);
    state = chatReducer(state, { type: "steps", id, steps: DECL });
    state = chatReducer(state, {
      type: "step",
      id,
      step: { id: "plan", state: "running", internals: [{ label: "a", value: "b" }] },
    });
    state = chatReducer(state, { type: "step", id, step: { id: "plan", state: "done" } });

    const step = state.find((it) => it.id === id)!.steps[0];
    expect(step.state).toBe("done");
    expect(step.internals).toEqual([{ label: "a", value: "b" }]);
  });
});
