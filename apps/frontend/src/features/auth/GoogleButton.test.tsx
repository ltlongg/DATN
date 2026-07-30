// @vitest-environment jsdom
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { ApiError } from "@/api/client";
import { GoogleButton } from "@/features/auth/GoogleButton";
import { useAuthStore } from "@/store/authStore";

const loginWithGoogle = vi.hoisted(() => vi.fn());
vi.mock("@/api/auth", () => ({ loginWithGoogle }));

// SDK Google Identity Services không chạy được trong jsdom -> thay bằng nút giả bắn ra
// credential y như thật.
vi.mock("@react-oauth/google", () => ({
  GoogleOAuthProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
  GoogleLogin: ({ onSuccess }: { onSuccess: (r: { credential?: string }) => void }) => (
    <button onClick={() => onSuccess({ credential: "id-token-gia" })}>Google giả</button>
  ),
}));

function renderButton() {
  return render(
    <MemoryRouter>
      <GoogleButton />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  loginWithGoogle.mockReset();
  vi.stubEnv("VITE_GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com");
  useAuthStore.setState({ token: null, user: null });
});

afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
  useAuthStore.setState({ token: null, user: null });
});

describe("GoogleButton", () => {
  it("gửi credential sang backend rồi lưu auth", async () => {
    loginWithGoogle.mockResolvedValue({
      access_token: "tok",
      token_type: "bearer",
      user: { id: "1", email: "gg@example.com", name: "Gờ", role: "user" },
    });
    renderButton();

    await userEvent.click(screen.getByRole("button", { name: "Google giả" }));

    expect(loginWithGoogle).toHaveBeenCalledWith("id-token-gia");
    await waitFor(() => expect(useAuthStore.getState().token).toBe("tok"));
  });

  it("409 account_link_required hiện message backend, không lưu auth", async () => {
    loginWithGoogle.mockRejectedValue(
      new ApiError(
        409,
        "account_link_required",
        "Email này đã đăng ký bằng mật khẩu. Hãy đăng nhập bằng mật khẩu.",
      ),
    );
    renderButton();

    await userEvent.click(screen.getByRole("button", { name: "Google giả" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Email này đã đăng ký bằng mật khẩu.",
    );
    expect(useAuthStore.getState().token).toBeNull();
  });

  it("chưa cấu hình client ID -> không render nút chết", () => {
    vi.stubEnv("VITE_GOOGLE_CLIENT_ID", "");
    renderButton();
    expect(screen.queryByRole("button", { name: "Google giả" })).not.toBeInTheDocument();
  });
});
