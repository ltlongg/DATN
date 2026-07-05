import { describe, expect, it } from "vitest";
import { lineDiff } from "@/features/prompts/diff";

describe("lineDiff", () => {
  it("mọi dòng giống nhau -> toàn same", () => {
    const rows = lineDiff("a\nb\nc", "a\nb\nc");
    expect(rows.every((r) => r.type === "same")).toBe(true);
    expect(rows.map((r) => r.text)).toEqual(["a", "b", "c"]);
  });

  it("thêm 1 dòng -> có add, giữ same còn lại", () => {
    const rows = lineDiff("a\nc", "a\nb\nc");
    expect(rows).toEqual([
      { type: "same", text: "a" },
      { type: "add", text: "b" },
      { type: "same", text: "c" },
    ]);
  });

  it("xoá 1 dòng -> có del", () => {
    const rows = lineDiff("a\nb\nc", "a\nc");
    expect(rows).toEqual([
      { type: "same", text: "a" },
      { type: "del", text: "b" },
      { type: "same", text: "c" },
    ]);
  });

  it("đổi 1 dòng -> del cũ + add mới", () => {
    const rows = lineDiff("a\nX\nc", "a\nY\nc");
    expect(rows.filter((r) => r.type === "del").map((r) => r.text)).toEqual(["X"]);
    expect(rows.filter((r) => r.type === "add").map((r) => r.text)).toEqual(["Y"]);
  });
});
