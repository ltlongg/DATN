// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { PrivacyModal } from "@/features/auth/PrivacyModal";
import { useAuthStore } from "@/store/authStore";
import type { User } from "@/types";

const { getMe, updatePreferences } = vi.hoisted(() => ({
  getMe: vi.fn(),
  updatePreferences: vi.fn(),
}));
vi.mock("@/api/auth", () => ({ getMe, updatePreferences }));

const USER: User = {
  id: "1",
  email: "u@example.com",
  name: "U",
  role: "user",
  share_conversations: false,
};

function renderModal() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <PrivacyModal onClose={() => {}} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  getMe.mockReset();
  updatePreferences.mockReset();
  useAuthStore.setState({ token: "t", user: USER });
});

afterEach(() => {
  cleanup();
  useAuthStore.setState({ token: null, user: null });
});

describe("PrivacyModal", () => {
  it("hiện trạng thái đọc từ server, mặc định tắt", async () => {
    getMe.mockResolvedValue(USER);
    renderModal();
    const box = await screen.findByRole("checkbox");
    await waitFor(() => expect(box).toBeEnabled());
    expect(box).not.toBeChecked();
  });

  it("bật chia sẻ -> gọi API và cập nhật user trong store", async () => {
    getMe.mockResolvedValue(USER);
    updatePreferences.mockResolvedValue({ ...USER, share_conversations: true });
    renderModal();
    const box = await screen.findByRole("checkbox");
    await waitFor(() => expect(box).toBeEnabled());

    await userEvent.click(box);

    expect(updatePreferences.mock.calls[0][0]).toEqual({ share_conversations: true });
    await waitFor(() => expect(box).toBeChecked());
    expect(useAuthStore.getState().user?.share_conversations).toBe(true);
  });
});
