// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ApiError } from "@/api/client";
import SettingsPage from "@/pages/SettingsPage";
import { useAuthStore } from "@/store/authStore";
import type { User } from "@/types";

const { getMe, updatePreferences, updateProfile, changePassword } = vi.hoisted(() => ({
  getMe: vi.fn(),
  updatePreferences: vi.fn(),
  updateProfile: vi.fn(),
  changePassword: vi.fn(),
}));
vi.mock("@/api/auth", () => ({ getMe, updatePreferences, updateProfile, changePassword }));

const USER: User = {
  id: "1",
  email: "u@example.com",
  name: "Người Dùng",
  role: "user",
  share_conversations: false,
  has_password: true,
};

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <SettingsPage />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  for (const fn of [getMe, updatePreferences, updateProfile, changePassword]) fn.mockReset();
  useAuthStore.setState({ token: "t", user: USER });
});

afterEach(() => {
  cleanup();
  useAuthStore.setState({ token: null, user: null });
});

describe("SettingsPage — thông tin cá nhân", () => {
  it("email chỉ xem; lưu họ tên -> gọi API (đã trim) và cập nhật store", async () => {
    getMe.mockResolvedValue(USER);
    updateProfile.mockResolvedValue({ ...USER, name: "Tên Mới" });
    renderPage();

    expect(await screen.findByLabelText("Email")).toBeDisabled();
    const save = screen.getByRole("button", { name: "Lưu thay đổi" });
    expect(save).toBeDisabled(); // chưa sửa gì

    const name = screen.getByLabelText("Họ tên");
    await userEvent.clear(name);
    await userEvent.type(name, "  Tên Mới ");
    await userEvent.click(save);

    expect(updateProfile.mock.calls[0][0]).toEqual({ name: "Tên Mới" });
    expect(await screen.findByText("Đã lưu thông tin cá nhân.")).toBeInTheDocument();
    expect(useAuthStore.getState().user?.name).toBe("Tên Mới");
  });
});

describe("SettingsPage — mật khẩu", () => {
  it("tài khoản Google-only không thấy mục đổi mật khẩu", async () => {
    getMe.mockResolvedValue({ ...USER, has_password: false });
    renderPage();
    await screen.findByLabelText("Họ tên");
    expect(screen.queryByLabelText("Mật khẩu hiện tại")).not.toBeInTheDocument();
  });

  it("xác nhận không khớp -> báo lỗi, không gọi API", async () => {
    getMe.mockResolvedValue(USER);
    renderPage();
    await userEvent.type(await screen.findByLabelText("Mật khẩu hiện tại"), "cu123456");
    await userEvent.type(screen.getByLabelText("Mật khẩu mới"), "moi123456");
    await userEvent.type(screen.getByLabelText("Xác nhận mật khẩu mới"), "khac12345");
    await userEvent.click(screen.getByRole("button", { name: "Đổi mật khẩu" }));

    expect(await screen.findByText("Mật khẩu xác nhận không khớp.")).toBeInTheDocument();
    expect(changePassword).not.toHaveBeenCalled();
  });

  it("sai mật khẩu hiện tại -> hiện message backend", async () => {
    getMe.mockResolvedValue(USER);
    changePassword.mockRejectedValue(
      new ApiError(400, "invalid_current_password", "Mật khẩu hiện tại không đúng."),
    );
    renderPage();
    await userEvent.type(await screen.findByLabelText("Mật khẩu hiện tại"), "sai");
    await userEvent.type(screen.getByLabelText("Mật khẩu mới"), "moi123456");
    await userEvent.type(screen.getByLabelText("Xác nhận mật khẩu mới"), "moi123456");
    await userEvent.click(screen.getByRole("button", { name: "Đổi mật khẩu" }));

    expect(changePassword.mock.calls[0][0]).toEqual({
      current_password: "sai",
      new_password: "moi123456",
    });
    expect(await screen.findByText("Mật khẩu hiện tại không đúng.")).toBeInTheDocument();
  });

  it("đổi thành công -> xoá trắng các ô", async () => {
    getMe.mockResolvedValue(USER);
    changePassword.mockResolvedValue({ ok: true });
    renderPage();
    const current = await screen.findByLabelText("Mật khẩu hiện tại");
    await userEvent.type(current, "cu123456");
    await userEvent.type(screen.getByLabelText("Mật khẩu mới"), "moi123456");
    await userEvent.type(screen.getByLabelText("Xác nhận mật khẩu mới"), "moi123456");
    await userEvent.click(screen.getByRole("button", { name: "Đổi mật khẩu" }));

    expect(await screen.findByText("Đã đổi mật khẩu.")).toBeInTheDocument();
    expect(current).toHaveValue("");
  });
});

describe("SettingsPage — quyền riêng tư", () => {
  it("hiện trạng thái đọc từ server, mặc định tắt", async () => {
    getMe.mockResolvedValue(USER);
    renderPage();
    const box = await screen.findByRole("checkbox");
    expect(box).toBeEnabled();
    expect(box).not.toBeChecked();
  });

  it("bật chia sẻ -> gọi API và cập nhật user trong store", async () => {
    getMe.mockResolvedValue(USER);
    updatePreferences.mockResolvedValue({ ...USER, share_conversations: true });
    renderPage();
    const box = await screen.findByRole("checkbox");

    await userEvent.click(box);

    expect(updatePreferences.mock.calls[0][0]).toEqual({ share_conversations: true });
    await waitFor(() => expect(box).toBeChecked());
    expect(useAuthStore.getState().user?.share_conversations).toBe(true);
  });
});
