// @vitest-environment jsdom
import { StrictMode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, waitFor } from "@testing-library/react";
import {
  readLastConversation,
  useRestoreLastConversation,
  writeLastConversation,
} from "@/features/chat/lastConversation";
import type { Message } from "@/types";

const getConversation = vi.hoisted(() => vi.fn());
vi.mock("@/api/chat", () => ({ getConversation }));

const USER = "u-1";
const MESSAGES = [{ id: "m1", role: "user", content: "Phùng Hưng?" }] as unknown as Message[];

/** Render hook DƯỚI StrictMode: đây chính là điều kiện làm lộ lỗi cờ huỷ ở cleanup. */
function renderRestore(busy = () => false) {
  const restore = vi.fn();
  function Probe() {
    useRestoreLastConversation(USER, busy, restore);
    return null;
  }
  render(
    <StrictMode>
      <Probe />
    </StrictMode>,
  );
  return restore;
}

beforeEach(() => {
  localStorage.clear();
  getConversation.mockReset();
});
afterEach(cleanup);

describe("nhớ phiên cuối", () => {
  it("ghi rồi đọc lại theo user; id null thì xoá", () => {
    writeLastConversation(USER, "c-1");
    expect(readLastConversation(USER)).toBe("c-1");
    expect(readLastConversation("u-khac")).toBeNull(); // key gắn theo user, không lẫn
    writeLastConversation(USER, null);
    expect(readLastConversation(USER)).toBeNull();
  });

  it("chưa đăng nhập thì không ghi và không đọc", () => {
    writeLastConversation(undefined, "c-1");
    expect(localStorage.length).toBe(0);
    expect(readLastConversation(undefined)).toBeNull();
  });
});

describe("useRestoreLastConversation", () => {
  it("mở lại phiên đã nhớ — kể cả dưới StrictMode (effect chạy hai lần)", async () => {
    writeLastConversation(USER, "c-1");
    getConversation.mockResolvedValue({ id: "c-1", messages: MESSAGES });

    const restore = renderRestore();

    await waitFor(() => expect(restore).toHaveBeenCalledWith("c-1", MESSAGES));
    expect(getConversation).toHaveBeenCalledTimes(1); // không fetch lại ở lần chạy thứ hai
  });

  it("chưa nhớ phiên nào -> không gọi API", async () => {
    renderRestore();
    await Promise.resolve();
    expect(getConversation).not.toHaveBeenCalled();
  });

  it("người dùng đã mở phiên khác trong lúc chờ -> không đè lên", async () => {
    writeLastConversation(USER, "c-1");
    getConversation.mockResolvedValue({ id: "c-1", messages: MESSAGES });

    const restore = renderRestore(() => true);

    await waitFor(() => expect(getConversation).toHaveBeenCalled());
    expect(restore).not.toHaveBeenCalled();
  });

  it("phiên đã bị xoá (API lỗi) -> quên id, lần sau không đòi lại", async () => {
    writeLastConversation(USER, "c-1");
    getConversation.mockRejectedValue(new Error("404"));

    const restore = renderRestore();

    await waitFor(() => expect(readLastConversation(USER)).toBeNull());
    expect(restore).not.toHaveBeenCalled();
  });
});
