// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement } from "react";
import { CitationList } from "@/features/chat/CitationList";
import * as chatApi from "@/api/chat";
import type { Citation } from "@/types";

vi.mock("@/api/chat");

// jsdom không có ResizeObserver, còn Radix Popper (nền của Tooltip) thì cần -> stub tối thiểu.
vi.stubGlobal(
  "ResizeObserver",
  class {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
);

afterEach(cleanup);
// KHÔNG clear/reset mock ở beforeEach: làm vậy rồi để mock reject thì Vitest đánh rơi
// rejection ra ngoài (unhandled error, fail test lỗi ở dưới). Mỗi test tự đặt hành vi mock
// của mình; test nào cần đếm số lần gọi thì tự clear ngay trong test đó.

/** SourceModal fetch qua TanStack Query -> cần provider. retry=false để test lỗi khỏi đợi. */
function renderWithQuery(ui: ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

const COLONIAL = "Thời kì thuộc địa";
const CAN_VUONG = "7. Phong trào Cần vương";

function cit(chunkId: string, leaf: string, quote?: string): Citation {
  return {
    chunk_id: chunkId,
    source_file: "lichsu.clean.md",
    start_line: 375,
    end_line: 378,
    heading_path: [COLONIAL, CAN_VUONG, leaf],
    quote,
  };
}

describe("CitationList", () => {
  it("không render gì khi không có nguồn", () => {
    const { container } = renderWithQuery(<CitationList citations={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("KHÔNG in tên file lẫn số dòng (chúng thuộc về modal, không thuộc danh sách)", () => {
    const { container } = renderWithQuery(
      <CitationList citations={[cit("c-1", "Bãi Sậy"), cit("c-2", "Lê Thành Phương")]} />
    );
    expect(container.textContent).not.toContain("lichsu.clean.md");
    expect(container.textContent).not.toContain("375");
    expect(container.textContent).not.toContain("378");
  });

  it("gộp theo mục, breadcrumb chung chỉ xuất hiện MỘT lần ở dòng chân", () => {
    renderWithQuery(
      <CitationList
        citations={[
          cit("c-1", "Lê Thành Phương"),
          cit("c-2", "Bãi Sậy"),
          cit("c-3", "Lê Thành Phương"),
        ]}
      />
    );
    expect(screen.getByText("Lê Thành Phương")).toBeInTheDocument();
    expect(screen.getByText("Bãi Sậy")).toBeInTheDocument();
    expect(screen.getByText(`${COLONIAL} › ${CAN_VUONG}`)).toBeInTheDocument();
    // 3 trích đoạn nhưng chỉ 2 mục -> 3 chip trên 2 dòng.
    expect(screen.getByText("3 trích đoạn · 2 mục")).toBeInTheDocument();
    expect(screen.getAllByRole("button")).toHaveLength(3);
  });

  it("chip giữ số thứ tự gốc sau khi gộp", () => {
    renderWithQuery(
      <CitationList
        citations={[
          cit("c-1", "Lê Thành Phương"),
          cit("c-2", "Bãi Sậy"),
          cit("c-3", "Lê Thành Phương"),
        ]}
      />
    );
    expect(screen.getAllByRole("button").map((b) => b.textContent)).toEqual([
      "[1]",
      "[3]",
      "[2]",
    ]);
  });

  it("chỉ 1 mục -> bỏ phần '· N mục' khỏi header", () => {
    renderWithQuery(<CitationList citations={[cit("c-1", "Bãi Sậy")]} />);
    expect(screen.getByText("1 trích đoạn")).toBeInTheDocument();
  });

  it("hover chip có quote -> tooltip hiện trích đoạn", async () => {
    const user = userEvent.setup();
    renderWithQuery(
      <CitationList citations={[cit("c-1", "Bãi Sậy", "Nghĩa quân Bãi Sậy lập căn cứ")]} />
    );
    await user.hover(screen.getByRole("button", { name: "[1]" }));
    await waitFor(() =>
      expect(screen.getAllByText(/Nghĩa quân Bãi Sậy lập căn cứ/).length).toBeGreaterThan(0)
    );
  });

  it("hover chip thiếu quote (message cũ) -> tooltip hiện gợi ý nhấn xem", async () => {
    const user = userEvent.setup();
    renderWithQuery(<CitationList citations={[cit("c-1", "Bãi Sậy")]} />);
    await user.hover(screen.getByRole("button", { name: "[1]" }));
    await waitFor(() =>
      expect(screen.getAllByText("Nhấn để xem nguồn").length).toBeGreaterThan(0)
    );
  });

  it("nhấn chip -> fetch ĐÚNG chunk của chip đó, modal hiện toàn văn + số dòng", async () => {
    const user = userEvent.setup();
    vi.mocked(chatApi.getSource).mockClear();
    vi.mocked(chatApi.getSource).mockResolvedValue({
      chunk_id: "c-2",
      text: "Nghĩa quân Bãi Sậy lập căn cứ ở vùng đầm lầy Hưng Yên.",
      heading_path: [COLONIAL, CAN_VUONG, "Bãi Sậy"],
      start_line: 375,
      end_line: 378,
    });
    renderWithQuery(
      <CitationList citations={[cit("c-1", "Lê Thành Phương"), cit("c-2", "Bãi Sậy")]} />
    );

    await user.click(screen.getByRole("button", { name: "[2]" }));

    expect(chatApi.getSource).toHaveBeenCalledExactlyOnceWith("c-2");
    expect(await screen.findByText(/vùng đầm lầy Hưng Yên/)).toBeInTheDocument();
    // Số dòng CHỈ được hiện ở đây (danh sách nguồn không in) -> đúng chỗ nó có nghĩa.
    expect(screen.getByText(/dòng 375–378/)).toBeInTheDocument();
    expect(screen.getByRole("dialog")).toHaveTextContent("Bãi Sậy");
  });

  it("fetch nguồn lỗi -> modal báo lỗi, không vỡ trang", async () => {
    const user = userEvent.setup();
    vi.mocked(chatApi.getSource).mockImplementation(async () => {
      throw new Error("404");
    });
    renderWithQuery(<CitationList citations={[cit("c-1", "Bãi Sậy")]} />);

    await user.click(screen.getByRole("button", { name: "[1]" }));

    expect(await screen.findByText(/Không tải được nguồn này/)).toBeInTheDocument();
  });
});
