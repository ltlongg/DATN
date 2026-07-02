import { useAuthStore } from "@/store/authStore";

const BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(
  /\/$/,
  "",
);

/** Lỗi API chuẩn — body backend là `{code, message}` (core/errors.py). */
export class ApiError extends Error {
  readonly code: string;
  readonly status: number;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

export type QueryValue = string | number | boolean | undefined | null;

export interface RequestOptions {
  method?: string;
  body?: unknown;
  query?: Record<string, QueryValue>;
  signal?: AbortSignal;
}

export function buildUrl(path: string, query?: Record<string, QueryValue>): string {
  const url = BASE_URL + path;
  if (!query) return url;
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== "") {
      params.append(key, String(value));
    }
  }
  const qs = params.toString();
  return qs ? `${url}?${qs}` : url;
}

/**
 * Fetch wrapper: gắn Bearer, gửi/nhận JSON, map lỗi `{code,message}` -> ApiError.
 * 401 -> clear auth store (RequireAuth sẽ điều hướng về /login), rồi ném ApiError.
 */
export async function apiFetch<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, query, signal } = opts;
  const headers: Record<string, string> = {};

  const token = useAuthStore.getState().token;
  if (token) headers.Authorization = `Bearer ${token}`;

  let payload: string | undefined;
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  const res = await fetch(buildUrl(path, query), { method, headers, body: payload, signal });

  if (res.status === 401) {
    useAuthStore.getState().clear();
    throw new ApiError(401, "unauthorized", "Phiên đăng nhập đã hết hạn.");
  }

  if (!res.ok) {
    const { code, message } = await parseError(res);
    throw new ApiError(res.status, code, message);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

async function parseError(res: Response): Promise<{ code: string; message: string }> {
  try {
    const data = (await res.json()) as { code?: string; message?: string };
    return {
      code: data.code ?? "error",
      message: data.message ?? "Có lỗi xảy ra.",
    };
  } catch {
    return { code: "error", message: `Lỗi ${res.status}.` };
  }
}
