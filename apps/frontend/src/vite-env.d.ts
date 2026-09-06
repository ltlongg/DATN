/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  /** OAuth client ID cho nút Sign in with Google. Rỗng/thiếu -> không render nút. */
  readonly VITE_GOOGLE_CLIENT_ID?: string;
  readonly VITE_APP_NAME?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
