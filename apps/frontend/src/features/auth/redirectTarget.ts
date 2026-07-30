/**
 * Đích điều hướng sau khi xác thực xong.
 *
 * `RequireAuth` lưu `state.from` (đường người dùng định vào trước khi bị đá về /login).
 * Trước đây không ai đọc nó — `useLogin` gọi `navigate("/")` cứng. Dùng chung cho cả
 * useLogin / useRegister / GoogleButton để logic chỉ nằm một chỗ.
 *
 * Chỉ nhận path nội bộ (bắt đầu bằng "/" và không phải "//" — chặn `//evil.com` bị trình
 * duyệt hiểu là URL tuyệt đối protocol-relative).
 */
const DEFAULT_AFTER_AUTH = "/";

export function redirectTargetFrom(state: unknown): string {
  const from = (state as { from?: unknown } | null)?.from;
  if (typeof from === "string" && from.startsWith("/") && !from.startsWith("//")) {
    return from;
  }
  return DEFAULT_AFTER_AUTH;
}
