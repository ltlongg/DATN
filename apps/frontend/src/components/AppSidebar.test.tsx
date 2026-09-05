// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AppSidebar } from "@/components/AppSidebar";
import { useAuthStore } from "@/store/authStore";
import { useUiStore } from "@/store/uiStore";
import type { User } from "@/types";

function renderSidebar(role: User["role"]) {
  const user: User = { id: "1", email: "u@example.com", name: "U", role };
  useAuthStore.setState({ token: "t", user });
  useUiStore.setState({ sidebarOpen: true });
  return render(
    <MemoryRouter>
      <AppSidebar />
    </MemoryRouter>,
  );
}

afterEach(() => {
  cleanup();
  useAuthStore.setState({ token: null, user: null });
});

describe("AppSidebar", () => {
  it("admin thấy đủ 3 nhóm và các mục quản trị", () => {
    renderSidebar("admin");
    // Nhãn nhóm
    for (const group of ["NỘI DUNG", "KHO TRI THỨC", "QUẢN TRỊ"]) {
      expect(screen.getByText(group)).toBeInTheDocument();
    }
    // Vài mục đại diện mỗi nhóm
    for (const label of ["Hỏi đáp", "Đoạn tài liệu", "Hội thoại", "Chi phí", "Hoạt động hệ thống", "Quản lý Prompt", "Cấu hình hệ thống"]) {
      expect(screen.getByRole("link", { name: label })).toBeInTheDocument();
    }
  });

  it("non-admin thấy đúng 2 mục khu user, không có nhóm/mục quản trị", () => {
    renderSidebar("user");
    expect(screen.getByRole("link", { name: "Hỏi đáp" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Dòng lịch sử" })).toHaveAttribute(
      "href",
      "/timeline",
    );
    expect(screen.getAllByRole("link")).toHaveLength(2);
    expect(screen.queryByText("QUẢN TRỊ")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Chi phí" })).not.toBeInTheDocument();
  });

  it("mục user KHÔNG trùng tên với mục admin (admin sẽ thấy cả hai cùng lúc)", () => {
    renderSidebar("admin");
    expect(screen.getByRole("link", { name: "Dòng lịch sử" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Dòng thời gian" })).toBeInTheDocument();
  });
});
