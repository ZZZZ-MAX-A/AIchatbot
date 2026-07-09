/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_OWNER_CONSOLE_API_BASE?: string;
  readonly VITE_OWNER_CONSOLE_HEALTH_PATH?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
