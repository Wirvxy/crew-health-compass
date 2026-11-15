/// <reference types="vite/client" />
interface ImportMetaEnv {
  /** Backend base URL. Leave unset to use the same origin (Vite's dev proxy). */
  readonly VITE_API_BASE_URL?: string
}
