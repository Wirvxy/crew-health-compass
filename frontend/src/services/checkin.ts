import type { CheckIn, DailyDraft } from '../types/assessment'
/** A submitted example can select its fixture only while every value matches that example. */
export function matchesSubmittedExample(record: CheckIn | undefined, example: Record<string, string | number>): boolean {
  return !!record && record.provenance === 'simulated' && Object.entries(example).every(([key, value]) => record.values[key as keyof DailyDraft] === String(value))
}
