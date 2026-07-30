// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import LoginPage from "@/pages/LoginPage";
import RegisterPage from "@/pages/RegisterPage";
import { useAuthStore } from "@/store/authStore";

// Nút Google có test riêng (GoogleButton.test.tsx); ở đây tắt hẳn để 2 trang auth không
// phụ thuộc VITE_GOOGLE_CLIENT_ID trong .env của từng máy.
vi.mock("@/features/auth/GoogleButton", () => ({ GoogleButton: () => null }));

/** Cây route rút gọn: chỉ 2 trang auth + stub cho khu hỏi đáp (đích redirect). */
function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/" element={<p>KHU HỎI ĐÁP</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  useAuthStore.setState({ token: null, user: null });
});

afterEach(() => {
  cleanup();
  useAuthStore.setState({ token: null, user: null });
});

describe("trang auth", () => {
  it("khách vào /register thấy form đăng ký, không bị đá đi", () => {
    renderAt("/register");
    expect(screen.getByRole("button", { name: "Đăng ký" })).toBeInTheDocument();
    expect(screen.getByLabelText("Họ tên")).toBeInTheDocument();
  });

  it("đã đăng nhập vào /register thì chuyển sang khu hỏi đáp", () => {
    useAuthStore.setState({ token: "tok", user: null });
    renderAt("/register");
    expect(screen.getByText("KHU HỎI ĐÁP")).toBeInTheDocument();
  });

  it("đã đăng nhập vào /login thì chuyển sang khu hỏi đáp", () => {
    useAuthStore.setState({ token: "tok", user: null });
    renderAt("/login");
    expect(screen.getByText("KHU HỎI ĐÁP")).toBeInTheDocument();
  });

  it("hai trang auth link qua lại được", () => {
    renderAt("/login");
    expect(screen.getByRole("link", { name: "Đăng ký" })).toHaveAttribute("href", "/register");
    cleanup();
    renderAt("/register");
    expect(screen.getByRole("link", { name: "Đăng nhập" })).toHaveAttribute("href", "/login");
  });
});
