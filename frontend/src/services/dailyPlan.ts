// "Plan for today": which daily tasks are done, per astronaut and per UTC day.
// Pure functions with no imports and no browser APIs, so tests/dailyPlan.test.ts can run them with Node's test runner.
// Only task flags and the time of the assessed check-in are kept here, never the readings themselves.

export type ManualTask = 'review'

export interface DayRecord {
  day: string // UTC date, YYYY-MM-DD
  checkin: { at: string; example: boolean } | null // a check-in the backend assessed successfully that day
  sleep: boolean // that day, an assessed check-in included sleep duration
  mood: boolean // that day, an assessed check-in included a mood
  review: boolean // ticked by the user
}
/** One record per astronaut ID: the latest day with progress. */
export type PlanStore = Record<string, DayRecord>

export const TASK_COUNT = 4
const DAY = /^\d{4}-\d{2}-\d{2}$/
const CREW_ID = /^[A-Za-z0-9_-]{1,64}$/

/** The UTC day (YYYY-MM-DD) of a time in milliseconds. A new day starts at 00:00 UTC. */
export const utcDay = (ms: number): string => new Date(ms).toISOString().slice(0, 10)

/** Milliseconds from `ms` until the next 00:00 UTC. */
export function msUntilNextUtcDay(ms: number): number {
  const d = new Date(ms)
  return Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate() + 1) - ms
}

export const emptyDay = (day: string): DayRecord => ({ day, checkin: null, sleep: false, mood: false, review: false })

/** One astronaut's progress on `day`. Anything saved on another day counts as nothing done. */
export function recordFor(store: PlanStore, crew: string, day: string): DayRecord {
  const saved = Object.hasOwn(store, crew) ? store[crew] : undefined
  return saved && saved.day === day ? saved : emptyDay(day)
}

/** Call only after the backend assessed a check-in. Optional tasks count only when that check-in included them. */
export function withCheckIn(store: PlanStore, crew: string, day: string, included: { sleep: boolean; mood: boolean }, example: boolean, at: string): PlanStore {
  const r = recordFor(store, crew, day)
  return { ...store, [crew]: { ...r, checkin: { at, example }, sleep: r.sleep || included.sleep, mood: r.mood || included.mood } }
}

/** A task the user ticks or unticks themself. */
export function withManual(store: PlanStore, crew: string, day: string, task: ManualTask, done: boolean): PlanStore {
  return { ...store, [crew]: { ...recordFor(store, crew, day), [task]: done } }
}

export const doneCount = (r: DayRecord): number => [r.checkin !== null, r.sleep, r.mood, r.review].filter(Boolean).length

/** Read saved progress defensively: malformed entries are dropped, and only plain crew IDs are kept as keys. */
export function parseStore(raw: string | null): PlanStore {
  let value: unknown
  try { value = raw ? JSON.parse(raw) : {} } catch { return {} }
  if (!value || typeof value !== 'object' || Array.isArray(value)) return {}
  const out: PlanStore = {}
  for (const [crew, entry] of Object.entries(value as Record<string, unknown>)) {
    const r = entry as Record<string, unknown> | null
    if (!CREW_ID.test(crew) || crew === '__proto__' || !r || typeof r !== 'object' || typeof r.day !== 'string' || !DAY.test(r.day)) continue
    const c = r.checkin as Record<string, unknown> | null | undefined
    const checkin = c && typeof c === 'object' && typeof c.at === 'string' && typeof c.example === 'boolean' ? { at: c.at, example: c.example } : null
    out[crew] = { day: r.day, checkin, sleep: checkin !== null && r.sleep === true, mood: checkin !== null && r.mood === true, review: r.review === true }
  }
  return out
}
