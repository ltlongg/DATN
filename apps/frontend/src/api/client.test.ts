// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiFetch } from "@/api/client";
import { useAuthStore } from "@/store/authStore";

function mockJsonResponse(status: number, body: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json" },
      }),
    ),
  );
}

beforeEach(() => {
  useAuthStore.setState({ token: null, user: null });
});

afterEach(() => {
  vi.unstubAllGlobals();
  useAuthStore.setState({ token: null, user: null });
});

describe("apiFetch — 401", () => {
  it("giữ nguyên code/message backend cho endpoint auth và KHÔNG xoá phiên", async () => {
    // Chốt bug cũ: mọi 401 đều bị nuốt thành "Phiên đăng nhập đã hết hạn" -> gõ sai mật
    // khẩu hiện sai message hoàn toàn.
    useAuthStore.setState({ token: "cu", user: null });
    mockJsonResponse(401, {
      code: "invalid_credentials",
      message: "Email hoặc mật khẩu không đúng.",
    });

    const err = await apiFetch("/api/auth/login", { method: "POST", body: {} }).catch(
      (e: unknown) => e,
    );

    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).code).toBe("invalid_credentials");
    expect((err as ApiError).message).toBe("Email hoặc mật khẩu không đúng.");
    expect(useAuthStore.getState().token).toBe("cu");
  });

  it("endpoint thường + có token -> coi là hết phiên, xoá auth store", async () => {
    useAuthStore.setState({ token: "cu", user: null });
    mockJsonResponse(401, { code: "unauthenticated", message: "Thiếu token." });

    const err = await apiFetch("/api/chat/conversations").catch((e: unknown) => e);

    expect((err as ApiError).code).toBe("unauthorized");
    expect(useAuthStore.getState().token).toBeNull();
  });

  it("endpoint thường nhưng CHƯA có token -> giữ message backend, không clear", async () => {
    mockJsonResponse(401, { code: "unauthenticated", message: "Thiếu token." });

    const err = await apiFetch("/api/chat/conversations").catch((e: unknown) => e);

    expect((err as ApiError).code).toBe("unauthenticated");
    expect((err as ApiError).message).toBe("Thiếu token.");
  });
});
