// Profile sessions (demo access control, docs/mode1-api.md): choosing a crew profile opens a session on the local
// backend. The browser keeps the session ID in an HttpOnly cookie that this code cannot read. There are no passwords.
import { API_BASE } from './api'

export interface Profile { astronaut_id: string; name: string }
export const PROFILE_HEADER = 'X-Crew-Health-Profile'
const OFFLINE = 'Cannot reach the local backend. Check that the API is running, then retry.'

/** A personal answer came without a valid session, or for another profile: the screen must not use it. */
export class SessionChanged extends Error {
  constructor() { super('Your session ended or another profile was opened.'); this.name = 'SessionChanged' }
}

// Tabs of the app tell each other when the session changes, so a hidden tab drops its workspace at once.
const channel = typeof BroadcastChannel === 'function' ? new BroadcastChannel('crew-health-compass-session') : null
const listeners = new Set<() => void>()
export function onSessionChange(listener: () => void) {
  listeners.add(listener)
  const fromOtherTab = () => listener()
  channel?.addEventListener('message', fromOtherTab)
  return () => { listeners.delete(listener); channel?.removeEventListener('message', fromOtherTab) }
}
/** This tab saw the session end or change: tell this tab's app, and the other tabs. */
function sessionChanged() { listeners.forEach(l => l()); channel?.postMessage('changed') }
export const announceSessionChange = () => channel?.postMessage('changed')

async function call(path: string, init: RequestInit = {}): Promise<Response> {
  try {
    return await fetch(`${API_BASE}${path}`, { ...init, credentials: 'same-origin', headers: { Accept: 'application/json', ...init.headers } })
  } catch (error) {
    if ((error as Error).name === 'AbortError') throw error
    throw new Error(OFFLINE)
  }
}
async function detail(response: Response, fallback: string): Promise<string> {
  try { const body = await response.json(); if (typeof body?.detail === 'string') return body.detail } catch { /* not JSON */ }
  return fallback
}
const isProfile = (v: unknown): v is Profile => !!v && typeof (v as Profile).astronaut_id === 'string' && typeof (v as Profile).name === 'string'

/** The profile of this browser's session, or null when there is none. */
export async function currentProfile(signal?: AbortSignal): Promise<Profile | null> {
  const response = await call('/api/session', { signal })
  if (!response.ok) throw new Error(await detail(response, `The session check failed (HTTP ${response.status}).`))
  const body = await response.json()
  if (body?.profile === null) return null
  if (!isProfile(body?.profile)) throw new Error('Unexpected session answer from the backend.')
  return body.profile
}

export async function listProfiles(signal?: AbortSignal): Promise<Profile[]> {
  const response = await call('/api/profiles', { signal })
  if (!response.ok) throw new Error(await detail(response, `Crew profiles could not be loaded (HTTP ${response.status}).`))
  const body = await response.json()
  if (!Array.isArray(body?.profiles) || !body.profiles.every(isProfile)) throw new Error('Unexpected profile list from the backend.')
  return body.profiles
}

export async function openProfile(astronautId: string): Promise<Profile> {
  const response = await call('/api/session', { method: 'POST', body: JSON.stringify({ astronaut_id: astronautId }), headers: { 'Content-Type': 'application/json' } })
  if (!response.ok) throw new Error(await detail(response, `The profile could not be opened (HTTP ${response.status}).`))
  const body = await response.json()
  if (!isProfile(body) || body.astronaut_id !== astronautId) throw new Error('Unexpected session answer from the backend.')
  return body
}

/** Log out: the backend forgets the session and removes the cookie. */
export async function endSession(): Promise<void> {
  const response = await call('/api/session', { method: 'DELETE' })
  if (!response.ok) throw new Error(await detail(response, `Logging out failed (HTTP ${response.status}).`))
}

/** Every personal request goes through here: the answer must belong to the profile this screen shows. */
export async function personalFetch(path: string, astronautId: string, init: RequestInit = {}): Promise<Response> {
  const response = await call(path, init)
  if (response.status === 401 || (response.ok && response.headers.get(PROFILE_HEADER) !== astronautId)) {
    sessionChanged()
    throw new SessionChanged()
  }
  return response
}
export { detail as errorDetail }

/** Short code shown on avatars: commander -> CDR, flight_engineer_2 -> FE2. */
export const profileCode = (id: string) => id === 'commander' ? 'CDR' : id.replace(/^flight_engineer_(\d+)$/, 'FE$1').toUpperCase().slice(0, 4)
