import { useEffect, useState } from 'react'
import { chartNumber, DatasetApiError } from '../services/dataset'
import type { DatasetPanel, Passport } from '../services/dataset'
type Service = { passport: (crew: string, visit: string, signal?: AbortSignal) => Promise<Passport> }
const words = (value: string) => value.replaceAll('_', ' ')
/** Display rounding only; the exact decimal string from the API stays in the tooltip. */
function num(value: string | null, signed = false) {
  const n = chartNumber(value)
  return n == null ? (value ?? '—') : <span title={`Exact: ${value}`}>{new Intl.NumberFormat('en-US', { maximumFractionDigits: 2, signDisplay: signed ? 'exceptZero' : 'auto' }).format(n)}</span>
}
const CATEGORY: Record<string, string> = { outside_lab_interval: 'Outside supplied lab interval', personal_baseline_change: 'Change from personal baseline', longitudinal_pattern: 'Longitudinal pattern', data_limitation: 'Data limitation' }
/** Lab "unavailable" means no supplied limits, which is not a missing reading. */
function labText(comparison: string, coverage: string) {
  if (comparison === 'unavailable') return 'Laboratory comparison unavailable'
  return coverage === 'lower_only' ? `${comparison} (lower limit only)` : coverage === 'upper_only' ? `${comparison} (upper limit only)` : comparison
}
interface Props { api: Service; crew: string; visit: string; onExplore: (panel: DatasetPanel, biomarker: string) => void }
/** A4 biological passport: A's response from D's API, shown as returned (decimal strings, units, provenance). */
export default function PassportSummary({ api, crew, visit, onExplore }: Props) {
  const key = `${crew}/${visit}`, postflight = visit.startsWith('R+')
  const [state, setState] = useState<{ key: string; data?: Passport; error?: string } | null>(null)
  useEffect(() => {
    if (!postflight) return
    const c = new AbortController()
    api.passport(crew, visit, c.signal).then(data => { if (!c.signal.aborted) setState({ key, data }) })
      .catch(e => { if (!c.signal.aborted) setState({ key, error: e instanceof DatasetApiError ? `Passport API ${e.status}: ${e.message}` : 'Unable to load the passport.' }) })
    return () => c.abort()
  }, [api, crew, visit, key, postflight])
  const p = state?.key === key ? state.data : undefined, error = state?.key === key ? state.error : undefined
  const head = <><p className="eyebrow">MODE 2 · NASA BIOLOGICAL PASSPORT / {crew} / {visit}</p><h2 id="passport-title">Biological passport</h2></>
  if (!postflight) return <section className="nasa-panel" aria-labelledby="passport-title">{head}<p className="nasa-muted">The passport covers postflight visits. Choose an R+ visit above.</p></section>
  if (error) return <section className="nasa-panel" aria-labelledby="passport-title" role="alert">{head}<p>{error}</p></section>
  if (!p) return <section className="nasa-panel" aria-labelledby="passport-title">{head}<p role="status">Loading the passport…</p></section>
  const lab = p.lab_interval_summary, status = p.measurement_status_counts
  return <section className="nasa-panel" aria-labelledby="passport-title">{head}
    <p className="nasa-note">Real NASA OSD-575 research data. Descriptive comparisons with this person's own preflight average and the supplied laboratory limits. Not a medically validated diagnostic system, and not a validation of the Mode 1 monitor.</p>
    <dl className="nasa-metrics">
      <div><dt>Biomarkers analysed</dt><dd>{p.total_biomarkers_considered}</dd><span>{p.complete_baseline_count} with a complete personal baseline · {p.insufficient_baseline_count} insufficient</span></div>
      <div><dt>Outside supplied lab interval</dt><dd>{(lab.below ?? 0) + (lab.above ?? 0)}</dd><span>{lab.below ?? 0} below · {lab.above ?? 0} above · {lab.within ?? 0} within</span></div>
      <div><dt>Laboratory comparison unavailable</dt><dd>{lab.unavailable ?? 0}</dd><span>No supplied limits. This is not a missing reading.</span></div>
      <div><dt>Missing or invalid readings</dt><dd>{(status.missing ?? 0) + (status.invalid ?? 0)}</dd><span>{status.missing ?? 0} missing · {status.invalid ?? 0} invalid</span></div>
    </dl>
    <h3>Panels</h3>
    <div className="nasa-table-scroll"><table><caption>Panel summaries for {p.astronaut_id} at {p.selected_visit}</caption><thead><tr><th>Panel</th><th>Group</th><th>Biomarkers</th><th>Complete baseline</th><th>Below / within / above lab interval</th><th>Lab comparison unavailable</th><th>Missing / invalid</th></tr></thead>
      <tbody>{p.panels.map(row => <tr key={row.panel}><th scope="row">{words(row.panel)}</th><td>{row.group}</td><td>{row.total_biomarkers_considered}</td><td>{row.complete_baseline_count}</td><td>{row.lab_interval_summary.below ?? 0} / {row.lab_interval_summary.within ?? 0} / {row.lab_interval_summary.above ?? 0}</td><td>{row.lab_interval_summary.unavailable ?? 0}</td><td>{row.measurement_status_counts.missing ?? 0} / {row.measurement_status_counts.invalid ?? 0}</td></tr>)}</tbody></table></div>
    <h3>Selected findings</h3>
    {p.trajectories.includes_later_observations && <p className="nasa-note">“{p.trajectories.label}”: trajectory classifications use the full postflight series, including visits after {p.selected_visit}.</p>}
    <div className="nasa-table-scroll"><table><caption>In the backend's order. The order is not a ranking of medical risk.</caption><thead><tr><th>Biomarker</th><th>Value</th><th>Personal baseline</th><th>Change</th><th>Laboratory comparison</th><th>{p.trajectories.label}</th><th>Finding</th><th><span className="sr-only">Chart</span></th></tr></thead>
      <tbody>{p.selected_findings.map(f => <tr key={`${f.panel}/${f.biomarker}`}><th scope="row">{words(f.biomarker)}<small className="nasa-muted"> · {words(f.panel)}</small></th><td>{f.current_value == null ? `No measurement (${f.current_value_status})` : <>{num(f.current_value)} <small>{f.unit}</small></>}</td><td>{f.baseline_value == null ? words(f.baseline_status) : num(f.baseline_value)}</td><td>{num(f.absolute_change, true)} <small className="nasa-muted">{words(f.change_direction)}</small></td><td>{labText(f.lab_comparison, f.interval_coverage)}</td><td>{f.trajectory_classification ? words(f.trajectory_classification) : 'No trajectory'}</td><td><strong>{CATEGORY[f.category] ?? words(f.category)}.</strong> {f.explanation}</td><td><button type="button" onClick={() => onExplore(f.panel, f.biomarker)}>Chart</button></td></tr>)}</tbody></table></div>
    <p className="nasa-muted">Trajectory classifications for all biomarkers: {Object.entries(p.trajectories.classification_counts).map(([k, v]) => `${words(k)} ${v}`).join(' · ')}.</p>
    <details><summary>Limitations ({p.limitations.length})</summary><ul>{p.limitations.map(l => <li key={l}>{l}</li>)}</ul></details>
    <details><summary>NASA source references</summary><p><a href={p.source_references.study_url} target="_blank" rel="noopener noreferrer">NASA OSD-575 study ↗</a></p><div className="nasa-table-scroll"><table><thead><tr><th>Panel</th><th>File</th><th>Row</th><th>Sample</th></tr></thead><tbody>{p.source_references.samples.map(s => <tr key={`${s.file}/${s.row}`}><td>{words(s.panel)}</td><td>{s.file}</td><td>{s.row}</td><td>{s.source_sample_id}</td></tr>)}</tbody></table></div></details>
  </section>
}
