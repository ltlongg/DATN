// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ActivityTab } from "@/features/advanced/ActivityTab";
import * as activityApi from "@/api/activity";
import type { ActivityLogResponse } from "@/types/admin";

vi.mock("@/api/activity");

const sample: ActivityLogResponse = {
  items: [
    {
      id: "1",
      created_at: "2026-07-05T09:12:03Z",
      request_id: "abcdef1234",
      user_id: "u1",
      method: "POST",
      path: "/api/chat/ask",
      status_code: 200,
      severity: "ok",
      latency_ms: 4210,
      error: null,
    },
    {
      id: "2",
      created_at: "2026-07-05T09:13:22Z",
      request_id: null,
      user_id: null,
      method: "GET",
      path: "/api/admin/kb/chunks/512",
      status_code: 500,
      severity: "error",
      latency_ms: 210,
      error: "ProgrammingError: AmbiguousColumn",
    },
  ],
  total: 2,
  limit: 50,
  offset: 0,
};

function renderTab() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ActivityTab />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("ActivityTab", () => {
  it("hiển thị các dòng log kèm path và lỗi", async () => {
    vi.mocked(activityApi.getActivity).mockResolvedValue(sample);
    renderTab();
    expect(await screen.findByText("/api/chat/ask")).toBeInTheDocument();
    expect(screen.getByText("/api/admin/kb/chunks/512")).toBeInTheDocument();
    expect(screen.getByText("ProgrammingError: AmbiguousColumn")).toBeInTheDocument();
  });

  it("đổi filter severity + áp dụng gọi lại API với severity=error", async () => {
    vi.mocked(activityApi.getActivity).mockResolvedValue(sample);
    renderTab();
    await screen.findByText("/api/chat/ask");

    const user = userEvent.setup();
    await user.selectOptions(screen.getByLabelText("Mức độ"), "error");
    await user.click(screen.getByRole("button", { name: "Áp dụng" }));

    await waitFor(() => {
      expect(activityApi.getActivity).toHaveBeenCalledWith(
        expect.objectContaining({ severity: "error" }),
      );
    });
  });
});
