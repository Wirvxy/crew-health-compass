// The signed-in astronaut's own stored check-ins and "Plan for today" (GET/PUT /api/me/...). The backend decides
// whose data it is from the session; the astronaut ID here is only used to check that the answer matches the screen.
import { checkResult, MonitoringApiError, request } from './monitoring'
import type { CheckInRequest, MonitoringResult } from './monitoring'

export interface StoredCheckIn { id: number; received_at: string; check_in: CheckInRequest; assessment: MonitoringResult }
export interface Plan {
  astronaut_id: string; day: string; done_count: number; task_count: number
  tasks: { checkin: { done: boolean; at: string | null }; sleep: { done: boolean }; mood: { done: boolean }; review: { done: boolean } }
}

const bad = (what: string) => new MonitoringApiError(500, `Unexpected ${what} answer from the backend.`)

export async function myCheckIns(astronautId: string, limit = 5, signal?: AbortSignal): Promise<StoredCheckIn[]> {
  const body = await request(`/api/me/checkins?limit=${limit}`, astronautId, { signal }) as { astronaut_id?: unknown; checkins?: unknown }
  if (body?.astronaut_id !== astronautId || !Array.isArray(body.checkins)) throw bad('check-in history')
  return (body.checkins as StoredCheckIn[]).map(c => {
    if (typeof c?.id !== 'number' || typeof c.received_at !== 'string' || c.check_in?.astronaut_id !== astronautId) throw bad('check-in history')
    return { ...c, assessment: checkResult(c.assessment) }
  })
}

export function checkPlan(value: unknown, astronautId: string, day: string): Plan {
  const p = value as Plan
  const flags = ['checkin', 'sleep', 'mood', 'review'] as const
  if (!p || p.astronaut_id !== astronautId || p.day !== day || typeof p.done_count !== 'number' || typeof p.task_count !== 'number'
    || !p.tasks || !flags.every(f => typeof p.tasks[f]?.done === 'boolean')) throw bad('plan')
  return p
}
export const myPlan = (astronautId: string, day: string, signal?: AbortSignal) =>
  request(`/api/me/plan?day=${encodeURIComponent(day)}`, astronautId, { signal }).then(v => checkPlan(v, astronautId, day))
export const markReview = (astronautId: string, day: string, done: boolean) =>
  request('/api/me/plan/review', astronautId, { method: 'PUT', body: JSON.stringify({ day, done }), headers: { 'Content-Type': 'application/json' } }).then(v => checkPlan(v, astronautId, day))
