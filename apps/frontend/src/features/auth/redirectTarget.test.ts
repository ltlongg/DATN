import { describe, expect, it } from "vitest";
import { redirectTargetFrom } from "@/features/auth/redirectTarget";

describe("redirectTargetFrom", () => {
  it("trả lại path RequireAuth đã lưu", () => {
    expect(redirectTargetFrom({ from: "/admin/logs" })).toBe("/admin/logs");
  });

  it("không có state / state lạ -> về khu hỏi đáp", () => {
    expect(redirectTargetFrom(null)).toBe("/");
    expect(redirectTargetFrom({})).toBe("/");
    expect(redirectTargetFrom({ from: 42 })).toBe("/");
  });

  it("từ chối URL ngoài (kể cả dạng protocol-relative)", () => {
    expect(redirectTargetFrom({ from: "https://evil.com" })).toBe("/");
    expect(redirectTargetFrom({ from: "//evil.com" })).toBe("/");
  });
});
