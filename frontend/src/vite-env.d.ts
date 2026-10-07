/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_AUTH_MODE?: string;
  readonly VITE_LOCAL_MOCK?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
