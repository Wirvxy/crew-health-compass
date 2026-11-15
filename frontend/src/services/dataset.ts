import { decodeDataset } from './datasetResponse'
/** Read-only transport validated against docs/osd575-api.md (PR #13). */
export const DATASET_PANELS = ['cmp', 'eve_cardiovascular', 'eve_immune', 'alamar_immune'] as const
export type DatasetPanel = typeof DATASET_PANELS[number]
export class DatasetApiError extends Error {
  status: number
  payload: unknown
  constructor(status: number, payload: unknown) {
    super(({404:'Crew, biomarker or postflight visit not found.',422:'A valid dataset panel is required.',503:'The local dataset is unavailable.'} as Record<number,string>)[status] || 'Dataset request failed.')
    this.name = 'DatasetApiError'
    this.status = status
    this.payload = payload
  }
}
/** Chart conversion only: keep the original serialized decimal beside this result. */
export function chartNumber(value: unknown): number | null {
  if (value == null || typeof value !== 'string' || !/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?$/i.test(value.trim())) return null
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}
type Counts = Record<string, number>
export interface PassportFinding {
  panel: DatasetPanel; group: string; biomarker: string; current_value: string | null; current_value_status: string; unit: string
  baseline_value: string | null; baseline_status: string; absolute_change: string | null; change_direction: string
  lab_comparison: string; interval_coverage: string; category: string; trajectory_classification: string | null; explanation: string
}
export interface Passport {
  study_id: 'OSD-575'; astronaut_id: string; selected_visit: string; data_origin: string
  total_biomarkers_considered: number; complete_baseline_count: number; insufficient_baseline_count: number; incompatible_units_count: number
  measurement_status_counts: Counts; lab_interval_summary: Counts & { coverage: Counts }
  panels: { panel: string; group: string; total_biomarkers_considered: number; complete_baseline_count: number; measurement_status_counts: Counts; lab_interval_summary: Counts }[]
  selected_findings: PassportFinding[]
  trajectories: { label: string; includes_later_observations: boolean; classification_counts: Counts }
  limitations: string[]; source_references: { study_url: string; samples: { panel: string; file: string; row: number; source_sample_id: string }[] }
}
function checkPassport(value: unknown): Passport {
  const p = value as Passport
  if (!p || p.study_id !== 'OSD-575' || !Array.isArray(p.panels) || !Array.isArray(p.selected_findings) || typeof p.trajectories?.includes_later_observations !== 'boolean') throw new DatasetApiError(500, value)
  return p
}
export function createDatasetService(origin = '', transport: typeof fetch = fetch) {
  const base = `${origin.replace(/\/$/, '')}/datasets/osd575`
  async function get(path: string, query?: {panel: DatasetPanel; biomarker?: string; visit?: string}, signal?: AbortSignal): Promise<unknown> {
    const params = new URLSearchParams()
    if (query) {
      if (!DATASET_PANELS.includes(query.panel)) throw new DatasetApiError(422, null)
      params.set('panel', query.panel)
      if (query.biomarker) params.set('biomarker', query.biomarker)
      if (query.visit) params.set('visit', query.visit)
    }
    return fetchJson(`${base}${path}${params.size ? `?${params}` : ''}`, signal)
  }
  async function fetchJson(url: string, signal?: AbortSignal): Promise<unknown> {
    const response = await transport(url, {signal, headers: {Accept:'application/json'}})
    if (!response.ok) { let payload: unknown = null; try { payload = await response.json() } catch { /* Non-JSON server errors are still HTTP errors. */ } throw new DatasetApiError(response.status, payload) }
    return response.json() // Preserve strings, nulls, units, statuses and provenance untouched.
  }
  const crewPath = (crew: string) => `/astronauts/${encodeURIComponent(crew)}`
  return {
    /** A4 passport (D's API). URLSearchParams sends the '+' in R+45 as %2B. */
    passport: (crew: string, visit: string, signal?: AbortSignal) => fetchJson(`${base}${crewPath(crew)}/passport?${new URLSearchParams({visit})}`, signal).then(checkPassport),
    trajectory: (crew: string, query: {panel: DatasetPanel; biomarker: string}, signal?: AbortSignal) => get(`${crewPath(crew)}/trajectory`, query, signal).then(value => decodeDataset('trajectory', value)),
    comparison: (query: {panel: DatasetPanel; biomarker: string}, signal?: AbortSignal) => get('/comparison', query, signal).then(value => decodeDataset('comparison', value)),
    astronauts: (signal?: AbortSignal) => get('/astronauts', undefined, signal).then(value => decodeDataset('astronauts', value)),
    panels: (signal?: AbortSignal) => get('/panels', undefined, signal).then(value => decodeDataset('panels', value)),
    measurements: (crew: string, query: {panel: DatasetPanel; biomarker?: string}, signal?: AbortSignal) => get(`${crewPath(crew)}/measurements`, query, signal).then(value => decodeDataset('measurements', value)),
    postflight: (crew: string, query: {panel: DatasetPanel; biomarker?: string; visit?: string}, signal?: AbortSignal) => get(`${crewPath(crew)}/postflight`, query, signal).then(value => decodeDataset('postflight', value)),
  }
}
