// Mission Environment transport for the radiation API (docs/radiation-api.md). The engine computes every
// statistic; this file only sends requests and checks the shapes it reads.
import { API_BASE } from './api'

export interface RadiationPoint {
  timestamp_utc: string; detector: string; value: string | null; value_status: 'valid' | 'missing' | 'invalid'
  raw_value: string; source_line: number; nasa_cdf_url: string
}
export interface RadiationStatistics {
  observation_count: number; valid_count: number; missing_count: number; invalid_count: number
  min: string | null; max: string | null; mean: string | null; median: string | null; first_to_last_change: string | null; peak: RadiationPoint | null
}
interface Series { detector: string; start_timestamp_utc: string | null; end_timestamp_utc: string | null; observation_count: number; observations: RadiationPoint[]; statistics: RadiationStatistics | null }
interface Metadata { dataset_id: string; data_origin: string; mission: string; instrument: string; measurement: string; unit: string; source: { csv_file: string; csv_sha256: string; dataset_url: string }; limitations: string[] }
export interface RadiationTimeline extends Metadata { start_date: string | null; end_date: string | null; observation_count: number; series: Series[] }
export interface RadiationEvent extends Metadata {
  event_date: string; title: string; source_reference: string; description: string; evidence_available: boolean
  series: (Series & { statistics: RadiationStatistics; preceding_week_comparison: { start_date: string; end_date: string; valid_sample_count: number; observed_date_count: number; median: string | null; event_median_to_prior_median_ratio: string | null } })[]
}

export class RadiationApiError extends Error {
  status: number
  constructor(status: number, detail: unknown) {
    super(typeof detail === 'string' ? detail : status === 503 ? 'The radiation dataset is not loaded on the server.' : `The radiation request failed (HTTP ${status}).`)
    this.name = 'RadiationApiError'; this.status = status
  }
}

async function get(path: string, signal?: AbortSignal): Promise<unknown> {
  let response: Response
  try { response = await fetch(`${API_BASE}/api/environment/radiation${path}`, { signal, headers: { Accept: 'application/json' } }) }
  catch (error) { if ((error as Error).name === 'AbortError') throw error; throw new RadiationApiError(0, 'Cannot reach the backend. Check that the local API is running, then retry.') }
  let body: unknown = null
  try { body = await response.json() } catch { /* A non-JSON error is still an HTTP error. */ }
  if (!response.ok) throw new RadiationApiError(response.status, (body as { detail?: unknown } | null)?.detail)
  return body
}
function check<T extends { unit?: unknown; series?: unknown }>(value: unknown): T {
  const v = value as T
  if (!v || typeof v.unit !== 'string' || !Array.isArray(v.series)) throw new RadiationApiError(500, 'Unexpected radiation response shape from the backend.')
  return v
}

/** Readings in an inclusive UTC date range (YYYY-MM-DD); omit both dates for the full record. */
export function radiationTimeline(range: { start?: string; end?: string }, signal?: AbortSignal) {
  const params = new URLSearchParams()
  if (range.start) params.set('start_date', range.start)
  if (range.end) params.set('end_date', range.end)
  params.set('include_statistics', 'true')
  return get(`/timeline${params.size ? `?${params}` : ''}`, signal).then(check<RadiationTimeline>)
}
export const may20Event = (signal?: AbortSignal) => get('/events/may-20-2024', signal).then(check<RadiationEvent>)

/** Display only: thousands separators on the exact decimal string, keeping every digit. */
export function withSeparators(raw: string | null | undefined): string {
  if (raw == null) return '—'
  const [whole, fraction] = raw.split('.')
  return `${whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}${fraction !== undefined ? `.${fraction}` : ''}`
}
/** "2024-05-20T06:15:19.000Z" -> "2024-05-20 06:15:19 UTC" */
export const utcLabel = (stamp: string) => `${stamp.slice(0, 10)} ${stamp.slice(11, 19)} UTC`
