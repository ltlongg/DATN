// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import CampaignPage from "@/pages/CampaignPage";

/**
 * Bản chiến dịch nhét markup SVG vào DOM bằng `dangerouslySetInnerHTML`, nên lỗi ở chỗ nối
 * dây (chuỗi rỗng, bấm địa điểm không ăn) sẽ KHÔNG lộ ra khi typecheck. Test này chỉ đi
 * đúng đường đó: dựng được trang, đổi cảnh/bước bằng nút, và bấm địa điểm trong markup.
 */
function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/chien-dich/dien-bien-phu-1954"]}>
      <Routes>
        <Route path="/chien-dich/:slug" element={<CampaignPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("CampaignPage", () => {
  afterEach(cleanup);

  it("dựng được bản chiến dịch rồi đổi cảnh và bước", async () => {
    renderPage();
    expect(await screen.findByRole("heading", { name: "Điện Biên Phủ" })).toBeInTheDocument();
    expect(screen.getByText("Đánh chắc, tiến chắc")).toBeInTheDocument();
    expect(document.querySelector(".world")?.innerHTML).toContain("dbp-bunker");

    fireEvent.click(screen.getByRole("button", { name: /Him Lam/ }));
    expect(screen.getByText("Mở cửa từ Him Lam")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Bộ binh tiến công/ }));
    expect(screen.getByText(/Đại đoàn 312 tiến công/)).toBeInTheDocument();
  });

  it("bấm địa điểm trong markup SVG nhảy đúng cảnh", async () => {
    renderPage();
    await screen.findByRole("heading", { name: "Điện Biên Phủ" });

    const a1 = document.querySelector('[data-site="a1"]');
    expect(a1).not.toBeNull();
    fireEvent.click(a1!.querySelector(".hit")!);
    expect(screen.getByText("Mở đường qua A1")).toBeInTheDocument();
  });

  it("slug lạ thì báo chưa có bản dựng", async () => {
    render(
      <MemoryRouter initialEntries={["/chien-dich/khong-co"]}>
        <Routes>
          <Route path="/chien-dich/:slug" element={<CampaignPage />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(await screen.findByText("Chưa có bản dựng cho chiến dịch này.")).toBeInTheDocument();
  });
});
