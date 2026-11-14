/** Backend base URL for every API call. Empty (default) means the same origin: Vite's dev proxy or a
 * same-origin deployment. Set VITE_API_BASE_URL at build time to use another server (it must then allow this origin). */
export const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')
