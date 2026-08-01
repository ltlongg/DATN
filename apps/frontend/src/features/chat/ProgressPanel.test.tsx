// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ProgressPanel } from "@/features/chat/ProgressPanel";
import type { ProgressStep } from "@/types";

afterEach(cleanup);

const STEPS: ProgressStep[] = [
  { id: "plan", label: "Phân tích câu hỏi", kind: "system", state: "done", detail: "Câu hỏi đơn · 1 bước" },
  { id: "todo:1", label: "Tìm Trương Định", kind: "retrieve", state: "done", detail: "Dense + BM25 + graph · 8 đoạn" },
  { id: "synthesize:1", label: "Soạn câu trả lời", kind: "system", state: "pending" },
];

describe("ProgressPanel", () => {
  it("không render gì khi chưa có bước nào (message user, message cũ trước B3)", () => {
    const { container } = render(
      <ProgressPanel steps={[]} startedAt={null} streaming={false} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("đang chạy thì mở sẵn, hiện đủ nhãn + dòng phụ", () => {
    render(<ProgressPanel steps={STEPS} startedAt={Date.now()} streaming />);
    expect(screen.getByText(/1\. Phân tích câu hỏi/)).toBeInTheDocument();
    expect(screen.getByText("Dense + BM25 + graph · 8 đoạn")).toBeInTheDocument();
    expect(screen.getByText("Ẩn tiến trình")).toBeInTheDocument();
  });

  it("xong thì tự gập thành một dòng, click mở lại được", async () => {
    render(<ProgressPanel steps={STEPS} startedAt={null} streaming={false} />);
    expect(screen.queryByText(/1\. Phân tích câu hỏi/)).not.toBeInTheDocument();
    expect(screen.getByText("Xem tiến trình")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button"));
    expect(screen.getByText(/1\. Phân tích câu hỏi/)).toBeInTheDocument();
  });

  it("đếm bước đã có kết — pending KHÔNG tính, nên không nói dối là N/N", () => {
    render(<ProgressPanel steps={STEPS} startedAt={null} streaming={false} />);
    expect(screen.getByText("Đã hoàn thành · 2/3 bước")).toBeInTheDocument();
  });

  it("message nạp lại từ DB thì tiêu đề KHÔNG kèm thời gian", () => {
    // V1 cố ý: thời gian đo client-side nên reload không dựng lại được (plan §7.3). Kiểm
    // bằng regex "kết thúc bằng số + s" để test hỏng nếu ai đó lỡ điền số 0 vào đây.
    render(<ProgressPanel steps={STEPS} startedAt={null} streaming={false} />);
    expect(screen.queryByText(/\d+(\.\d+)?s$/)).not.toBeInTheDocument();
  });

  it("lượt vừa chạy xong thì có kèm thời gian", () => {
    render(<ProgressPanel steps={STEPS} startedAt={Date.now() - 2500} streaming={false} />);
    expect(screen.getByText(/^Đã hoàn thành · 2\/3 bước · 2\.5s$/)).toBeInTheDocument();
  });

  it("dòng đang chạy có nhãn trợ năng riêng, không chỉ khác màu", () => {
    const running: ProgressStep[] = [
      { id: "plan", label: "Phân tích câu hỏi", kind: "system", state: "running" },
    ];
    render(<ProgressPanel steps={running} startedAt={null} streaming />);
    expect(screen.getByLabelText("đang chạy")).toBeInTheDocument();
  });

  it("bước bị bỏ có nhãn riêng, phân biệt được với bước chưa chạy", () => {
    // Todo list dừng sớm (B4): "hệ thống cân nhắc rồi bỏ" khác hẳn "chưa tới lượt", và
    // người dùng chỉ đọc được khác biệt đó nếu hai state có nhãn trợ năng khác nhau.
    const stopped: ProgressStep[] = [
      { id: "todo:1", label: "Xác định mắt xích", kind: "retrieve", state: "partial" },
      { id: "todo:2", label: "Tra tiếp", kind: "retrieve", state: "skipped" },
      { id: "synthesize:1", label: "Soạn câu trả lời", kind: "system", state: "pending" },
    ];
    render(<ProgressPanel steps={stopped} startedAt={null} streaming />);
    expect(screen.getByLabelText("đã bỏ qua")).toBeInTheDocument();
    expect(screen.getByLabelText("chưa chạy")).toBeInTheDocument();
  });

  it("bước bị bỏ KHÔNG tính là đã có kết", () => {
    const stopped: ProgressStep[] = [
      { id: "todo:1", label: "Xác định mắt xích", kind: "retrieve", state: "partial" },
      { id: "todo:2", label: "Tra tiếp", kind: "retrieve", state: "skipped" },
    ];
    render(<ProgressPanel steps={stopped} startedAt={null} streaming={false} />);
    expect(screen.getByText("Đã hoàn thành · 1/2 bước")).toBeInTheDocument();
  });
});

/**
 * Tầng 2 thay hẳn DebugPanel (xoá 2026-08-01). Điều kiện hiện = `internals` CÓ MẶT, không
 * phải role: backend đã bóc field đó cho mọi lượt không phải admin-bật-debug, nên hỏi role
 * lần nữa ở frontend chỉ đẻ thêm một nguồn sự thật thứ hai để lệch.
 */
describe("ProgressPanel — tầng 2 (internals)", () => {
  const WITH_INTERNALS: ProgressStep[] = [
    {
      id: "plan",
      label: "Phân tích câu hỏi",
      kind: "system",
      state: "done",
      detail: "Câu hỏi đơn · 1 bước",
      internals: [
        { label: "Câu viết lại", value: "Trương Định là ai?" },
        { label: "Định tuyến", value: "needs_retrieval" },
      ],
    },
    { id: "todo:1", label: "Tìm Trương Định", kind: "retrieve", state: "done" },
  ];

  it("bước có internals mở ra bảng số liệu, gập sẵn lúc đầu", async () => {
    render(<ProgressPanel steps={WITH_INTERNALS} startedAt={null} streaming />);
    expect(screen.queryByText("Trương Định là ai?")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /Phân tích câu hỏi/ }));
    expect(screen.getByText("Câu viết lại")).toBeInTheDocument();
    expect(screen.getByText("Trương Định là ai?")).toBeInTheDocument();
    expect(screen.getByText("needs_retrieval")).toBeInTheDocument();
  });

  it("bước KHÔNG có internals thì không mọc nút mở rộng", () => {
    render(<ProgressPanel steps={WITH_INTERNALS} startedAt={null} streaming />);
    expect(
      screen.queryByRole("button", { name: /Tìm Trương Định/ }),
    ).not.toBeInTheDocument();
    expect(screen.getByText(/2\. Tìm Trương Định/)).toBeInTheDocument();
  });

  it("người dùng thường (backend đã bóc internals) thấy panel y như cũ", () => {
    const stripped = WITH_INTERNALS.map(({ internals: _drop, ...s }) => s);
    render(<ProgressPanel steps={stripped} startedAt={null} streaming />);
    // Chỉ còn đúng nút gập/mở của cả panel, không nút nào của từng bước.
    expect(screen.getAllByRole("button")).toHaveLength(1);
    expect(screen.getByText(/1\. Phân tích câu hỏi/)).toBeInTheDocument();
  });
});
