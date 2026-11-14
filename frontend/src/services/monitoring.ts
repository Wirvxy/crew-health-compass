// Mode 1 transport for D's API (docs/mode1-api.md). The backend does all assessment; this file only sends and checks shapes.
import { API_BASE } from './api'

export const CONTEXTS = ['rest', 'exercise', 'recovery', 'morning_check', 'inflight_vitals_check', 'other'] as const
export type ActivityContext = typeof CONTEXTS[number]
export const MOODS = ['low', 'fair', 'good', 'great'] as const
type Quantity = { value: string; unit: string }
export interface CheckInRequest {
  astronaut_id: string; timestamp: string; activity_context: ActivityContext; data_origin: 'user'
  indicators: { heart_rate: Quantity; respiratory_rate: Quantity; systolic_bp: Quantity; diastolic_bp: Quantity; sleep_duration?: Quantity; mood?: string }
}
export interface Statistics {
  mad: string | null; absolute_deviation: string | null; robust_z: string | null; status: 'normal' | 'unusual' | 'insufficient_data'
  anomaly: boolean | null; observation_count: number; history_span_days: string | null; trend_slope_per_day: string | null; history_origins: string[]
}
export interface Evidence { indicator: string; unit: string; value: string | null; baseline?: string | null; category?: string; statistics?: Statistics }
export interface MonitoringResult {
  astronaut_id: string; timestamp: string; activity_context: string; data_origin: string
  overall_status: 'normal' | 'unusual' | 'insufficient_data' | 'rule_supported_warning'
  affected_systems: string[]; body_marker: string | null; evidence: Evidence[]
  statistical_findings: string[]; optional_ml_findings: unknown; explanation: string
  next_action_protocol_id: string | null; insufficient_data: string[]; approved_rule_id?: string | null
}
export interface HistoryRange { activity_context: string; observations: number; first: string; last: string }
export interface MonitoringAstronauts { data_origin: string; note: string; manual_contexts: string[]; astronauts: { astronaut_id: string; history: HistoryRange[] }[] }

export class MonitoringApiError extends Error {
  status: number
  constructor(status: number, detail: unknown) {
    super(typeof detail === 'string' ? detail : status === 503 ? 'The Mode 1 history is not loaded on the server.' : `The monitoring request failed (HTTP ${status}).`)
    this.name = 'MonitoringApiError'; this.status = status
  }
}

async function request(path: string, init: RequestInit): Promise<unknown> {
  let response: Response
  try { response = await fetch(`${API_BASE}/api/monitoring${path}`, { ...init, headers: { Accept: 'application/json', ...init.headers } }) }
  catch (error) { if ((error as Error).name === 'AbortError') throw error; throw new MonitoringApiError(0, 'Cannot reach the backend. Check that the local API is running, then retry.') }
  let body: unknown = null
  try { body = await response.json() } catch { /* A non-JSON error is still an HTTP error. */ }
  if (!response.ok) throw new MonitoringApiError(response.status, (body as { detail?: unknown } | null)?.detail)
  return body
}

const STATUSES = ['normal', 'unusual', 'insufficient_data', 'rule_supported_warning']
function checkResult(value: unknown): MonitoringResult {
  const r = value as MonitoringResult
  const ok = !!r && STATUSES.includes(r.overall_status) && Array.isArray(r.evidence) && Array.isArray(r.insufficient_data)
    && Array.isArray(r.affected_systems) && (r.body_marker === null || typeof r.body_marker === 'string') && typeof r.explanation === 'string'
  if (!ok) throw new MonitoringApiError(500, 'Unexpected assessment shape from the backend.')
  return r
}

export const monitoringAstronauts = (signal?: AbortSignal) => request('/astronauts', { signal }) as Promise<MonitoringAstronauts>
export const assessCheckIn = (body: CheckInRequest, signal?: AbortSignal) =>
  request('/assess', { method: 'POST', body: JSON.stringify(body), headers: { 'Content-Type': 'application/json' }, signal }).then(checkResult)

/** Display only: maps the backend's status to the existing status styles. Red is reserved for an approved rule. */
export const STATUS_VIEW = {
  normal: { tone: 'normal', label: 'No unusual pattern' },
  unusual: { tone: 'watch', label: 'Unusual vs personal history' },
  insufficient_data: { tone: 'unavailable', label: 'Not assessed' },
  rule_supported_warning: { tone: 'action', label: 'Approved rule warning' },
} as const
export const words = (value: string) => value.replaceAll('_', ' ')
