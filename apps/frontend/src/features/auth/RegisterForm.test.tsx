// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { ApiError } from "@/api/client";
import { RegisterForm } from "@/features/auth/RegisterForm";
import { useAuthStore } from "@/store/authStore";

const register = vi.hoisted(() => vi.fn());
vi.mock("@/api/auth", () => ({ register }));

beforeEach(() => {
  register.mockReset();
  useAuthStore.setState({ token: null, user: null });
});

afterEach(() => {
  cleanup();
  useAuthStore.setState({ token: null, user: null });
});

async function fillAndSubmit() {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Họ tên"), "  Người Mới  ");
  await user.type(screen.getByLabelText("Email"), "  moi@example.com  ");
  await user.type(screen.getByLabelText("Mật khẩu"), "secret123");
  await user.type(screen.getByLabelText("Mật khẩu xác nhận"), "secret123");
  await user.click(screen.getByRole("button", { name: "Đăng ký" }));
}

describe("RegisterForm", () => {
  it("submit gọi API đúng payload (đã trim) và lưu auth", async () => {
    register.mockResolvedValue({
      access_token: "tok",
      token_type: "bearer",
      user: { id: "1", email: "moi@example.com", name: "Người Mới", role: "user" },
    });
    render(
      <MemoryRouter>
        <RegisterForm />
      </MemoryRouter>,
    );

    await fillAndSubmit();

    expect(register).toHaveBeenCalledWith("moi@example.com", "Người Mới", "secret123");
    await waitFor(() => expect(useAuthStore.getState().token).toBe("tok"));
  });

  it("mật khẩu xác nhận không khớp -> báo lỗi, KHÔNG gọi API", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <RegisterForm />
      </MemoryRouter>,
    );

    await user.type(screen.getByLabelText("Họ tên"), "Người Mới");
    await user.type(screen.getByLabelText("Email"), "moi@example.com");
    await user.type(screen.getByLabelText("Mật khẩu"), "secret123");
    await user.type(screen.getByLabelText("Mật khẩu xác nhận"), "secret999");
    await user.click(screen.getByRole("button", { name: "Đăng ký" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Mật khẩu xác nhận không khớp.");
    expect(register).not.toHaveBeenCalled();
  });

  it("lỗi 409 hiện message tiếng Việt của backend", async () => {
    register.mockRejectedValue(new ApiError(409, "email_taken", "Email này đã được đăng ký."));
    render(
      <MemoryRouter>
        <RegisterForm />
      </MemoryRouter>,
    );

    await fillAndSubmit();

    expect(await screen.findByRole("alert")).toHaveTextContent("Email này đã được đăng ký.");
    expect(useAuthStore.getState().token).toBeNull();
  });
});
