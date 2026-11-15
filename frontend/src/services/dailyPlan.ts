// "Plan for today" day rule: a mission day is a UTC calendar day, so the plan resets at 00:00 UTC.
// The progress itself is stored per profile on the backend (GET /api/me/plan). Pure functions with no imports,
// so tests/dailyPlan.test.ts can run them with Node's test runner.

/** The UTC day (YYYY-MM-DD) of a time in milliseconds. A new day starts at 00:00 UTC. */
export const utcDay = (ms: number): string => new Date(ms).toISOString().slice(0, 10)

/** Milliseconds from `ms` until the next 00:00 UTC. */
export function msUntilNextUtcDay(ms: number): number {
  const d = new Date(ms)
  return Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate() + 1) - ms
}
