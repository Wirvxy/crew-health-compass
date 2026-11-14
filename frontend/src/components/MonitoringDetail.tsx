import StatusLabel from './StatusLabel'
import { evidenceView } from './BodyMap'
import { STATUS_VIEW, words } from '../services/monitoring'
import type { MonitoringResult } from '../services/monitoring'
interface Props { result: MonitoringResult | null; selected: string | null; example: boolean; onSelect: (indicator: string) => void }
/** Evidence for one measurement, shown exactly as the backend returned it (decimal strings, units, reasons). */
export default function MonitoringDetail({ result, selected, example, onSelect }: Props) {
  if (!result) return <section className="panel detail-panel" aria-labelledby="detail-name"><div className="system-detail"><p className="eyebrow">03 / WHY? WHAT SHOULD I DO?</p><h2 id="detail-name">Evidence</h2><div className="empty-state"><strong>No assessment yet.</strong>Submit the daily check-in. The evidence behind the result will appear here.</div></div></section>
  const item = result.evidence.find(e => e.indicator === selected) ?? result.evidence.find(e => e.statistics?.anomaly) ?? result.evidence[0]
  const stats = item?.statistics, view = item ? evidenceView(item) : STATUS_VIEW[result.overall_status]
  const reasons = result.insufficient_data.filter(r => item && r.startsWith(`${item.indicator}:`))
  const findings = result.statistical_findings.filter(f => item && f.startsWith(`${item.indicator} `))
  const row = (label: string, value: string | number | null | undefined, unit = '') => <tr><th scope="row">{label}</th><td>{value == null ? 'Unavailable' : `${value}${unit ? ` ${unit}` : ''}`}</td></tr>
  return <section className="panel detail-panel" aria-labelledby="detail-name"><div className="system-detail" key={`${result.timestamp}-${item?.indicator}`}>
    <div className="detail-title"><div><p className="eyebrow">03 / WHY? WHAT SHOULD I DO?</p><h2 id="detail-name">{item ? words(item.indicator) : 'Evidence'}</h2></div><StatusLabel status={view.tone} label={view.label} /></div>
    <p className="provenance">Statistical comparison with synthetic personal history · {words(result.astronaut_id)} · {words(result.activity_context)}{example ? ' · example values' : ''}</p>
    <div className="marker-select"><label htmlFor="evidence-select">Measurement</label><select id="evidence-select" value={item?.indicator ?? ''} onChange={e => onSelect(e.target.value)}>{result.evidence.map(e => <option key={e.indicator} value={e.indicator}>{words(e.indicator)} · {evidenceView(e).label}</option>)}</select></div>
    {item && <div className="current-grid"><div><span className="current-label">CURRENT ({words(result.activity_context).toUpperCase()})</span><div className="number">{item.value ?? item.category ?? '—'} <small>{item.value != null ? item.unit : ''}</small></div><span className="micro">Entered at check-in</span></div><div><span className="current-label">PERSONAL BASELINE</span><div className="number baseline-number">{item.baseline ?? '—'} <small>{item.baseline != null ? item.unit : ''}</small></div><span className="micro">{stats?.observation_count ? `Median of ${stats.observation_count} earlier readings` : 'No baseline'}</span></div></div>}
    <section className="info-section"><div className="section-label"><span className="step-num">01</span> HOW DIFFERENT IS IT?</div>
      {stats && stats.status !== 'insufficient_data' ? <table className="data-table"><tbody>{row('Difference from baseline', stats.absolute_deviation, item?.unit)}{row('Robust z-score', stats.robust_z)}{row('Spread of history (MAD)', stats.mad, item?.unit)}{row('Earlier readings used', stats.observation_count)}{row('History span', stats.history_span_days, 'days')}{row('History trend', stats.trend_slope_per_day, `${item?.unit} per day`)}{row('History source', stats.history_origins.join(', '))}</tbody></table>
        : <p>Not compared. {reasons.join(' ') || 'No comparable history for this measurement.'}</p>}</section>
    <section className="info-section"><div className="section-label"><span className="step-num">02</span> WHAT THE BACKEND FOUND</div><p>{findings.join(' ') || (stats?.status === 'normal' ? 'No finding for this measurement: it did not exceed the statistical threshold.' : 'No finding: this measurement was not compared.')}</p></section>
    <section className="action-box"><div className="section-label"><span className="step-num">03</span> NEXT ACTION</div><p>{result.next_action_protocol_id ? `Approved protocol: ${result.next_action_protocol_id}` : 'No approved action protocol is available. This is an exploratory monitoring finding, not a diagnosis.'}</p></section>
    {result.insufficient_data.length > 0 && <details className="info-section" open={result.overall_status !== 'unusual'}><summary>Limitations of this assessment ({result.insufficient_data.length})</summary><ul className="details-note">{result.insufficient_data.map(r => <li key={r}>{r}</li>)}</ul></details>}
    <p className="details-note">Overall: {result.explanation} History: Person B's synthetic ISS dataset (fictional crew and readings). Method: A's M2 personal robust statistics (median and MAD); the M3 machine-learning model is off.</p>
  </div></section>
}
