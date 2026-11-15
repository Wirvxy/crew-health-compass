// View models for the Mode 1 check-in form. The backend's request and response types are in services/monitoring.ts.
export type Status = 'normal' | 'watch' | 'action' | 'unavailable'
export type DailyField = 'context' | 'timestamp' | 'heart' | 'respiratory' | 'systolic' | 'diastolic' | 'sleep' | 'mood'
export type DailyDraft = Record<DailyField, string>
export interface CheckIn {
  astronautId: string; values: DailyDraft; provenance: 'user' | 'simulated'; timestamp: string
}
export interface CrewDraft { values: DailyDraft; simulated: boolean }
