// Where "Plan for today" progress lives: memory, plus this browser's localStorage so it survives a reload.
// The app has no other saved state (drafts and results stay in memory), and the backend does not store
// check-ins yet, so the browser keeps only task flags and the time of each assessed check-in, never readings.
import { useSyncExternalStore } from 'react'
import { parseStore, utcDay, withCheckIn, withManual } from './dailyPlan'
import type { ManualTask, PlanStore } from './dailyPlan'

export const STORAGE_KEY = 'crew-health-compass.plan-for-today.v1'
let current: PlanStore | null = null
const listeners = new Set<() => void>()

function read(): PlanStore {
  try { return parseStore(localStorage.getItem(STORAGE_KEY)) } catch { return {} } // storage blocked: start empty
}
const snapshot = (): PlanStore => (current ??= read())
function save(next: PlanStore) {
  current = next
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(next)) } catch { /* private window or full storage: kept until reload */ }
  listeners.forEach(listener => listener())
}
function subscribe(listener: () => void) {
  listeners.add(listener)
  // Another tab of the app changed the progress.
  const onStorage = (e: StorageEvent) => { if (e.key === STORAGE_KEY || e.key === null) { current = read(); listener() } }
  window.addEventListener('storage', onStorage)
  return () => { listeners.delete(listener); window.removeEventListener('storage', onStorage) }
}

export const usePlanStore = () => useSyncExternalStore(subscribe, snapshot)

/** Call only after the backend assessed a check-in. It counts for the UTC day on which the assessment came back. */
export function recordAssessedCheckIn(crew: string, included: { sleep: boolean; mood: boolean }, example: boolean) {
  const now = Date.now()
  save(withCheckIn(snapshot(), crew, utcDay(now), included, example, new Date(now).toISOString()))
}

export function setManualTask(crew: string, day: string, task: ManualTask, done: boolean) {
  save(withManual(snapshot(), crew, day, task, done))
}
