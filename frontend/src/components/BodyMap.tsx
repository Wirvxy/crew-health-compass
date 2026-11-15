import { useMemo } from 'react'
import Astronaut3D from './Astronaut3D'
import type { HealthLocation, HealthSignal } from './astronautHealth'
import StatusLabel from './StatusLabel'
import { STATUS_VIEW, words } from '../services/monitoring'
import type { Evidence, MonitoringResult } from '../services/monitoring'
interface Props { result: MonitoringResult | null; selected: string | null; onSelect: (indicator: string) => void }
// Display locations follow the Mode 1 body-system mapping documented by A and D.
const LOCATIONS: Record<string, HealthLocation> = {
  heart_rate: 'chest', systolic_bp: 'chest', diastolic_bp: 'chest',
  respiratory_rate: 'lungs', sleep_duration: 'head', mood: 'head',
}
/** Display only: each evidence item's own status from the backend. */
export const evidenceView = (item: Evidence) => STATUS_VIEW[item.statistics?.status ?? 'insufficient_data']
export default function BodyMap({ result, selected, onSelect }: Props) {
  const view = result ? STATUS_VIEW[result.overall_status] : null
  const flagged = result?.evidence.find(e => e.statistics?.anomaly)?.indicator ?? null
  const item = result?.evidence.find(e => e.indicator === selected)
    ?? result?.evidence.find(e => e.indicator === flagged)
    ?? result?.evidence[0]
  const signals = useMemo<HealthSignal[]>(() => {
    if (!result) return []
    const values: HealthSignal[] = result.evidence.flatMap(e => {
      const location = LOCATIONS[e.indicator]
      if (!location) return []
      return [{
        id: e.indicator, label: words(e.indicator),
        value: e.value === null ? (e.category ?? 'No reading') : `${new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 }).format(Number(e.value))} ${e.unit}`,
        location, tone: evidenceView(e).tone,
        message: e.statistics?.status === 'normal' ? 'No unusual pattern' : e.statistics?.status === 'unusual' ? 'Outside personal pattern' : 'Not assessed',
      }]
    })
    if (result.overall_status === 'rule_supported_warning' && result.body_marker && ['head', 'chest', 'lungs'].includes(result.body_marker)) {
      values.push({ id: 'approved-warning', label: 'Approved warning', value: result.approved_rule_id ?? 'Rule-supported warning', location: result.body_marker as HealthLocation, tone: 'action', message: result.explanation })
    }
    return values
  }, [result])
  const compared = result?.evidence.filter(e => e.statistics && e.statistics.status !== 'insufficient_data').length ?? 0
  const banner = !result ? 'No check-in assessed yet. Submit the daily check-in first.'
    : result.overall_status === 'unusual' ? `A measurement differs from earlier readings. Review the evidence for ${result.affected_systems.map(words).join(', ')}.`
    : result.overall_status === 'normal' ? `No unusual pattern among ${compared} compared measurement${compared === 1 ? '' : 's'}. Check the limitations too.`
    : result.overall_status === 'insufficient_data' ? 'Not assessed: comparable history is missing or too short. This is unknown, not normal.'
    : 'Warning from an approved rule.'
  return <section className="panel map-panel" aria-labelledby="map-title"><div className="map-header"><div className="panel-intro"><div><p className="eyebrow">02 / CREW VISUALIZATION</p><h2 id="map-title">Your astronaut, in 3D.</h2></div><span className="zone-number">360° VIEW</span></div><p className="description">Assessment colors follow each body region. Select a floating metric to inspect its evidence. Colors reflect the backend comparison with synthetic personal history.</p>
    <div className="assessment-banner assessment-card" data-tone={view?.tone ?? 'unavailable'} role="status" aria-live="polite" aria-atomic="true">
      <div className="assessment-card-heading"><span className="eyebrow">LATEST ASSESSMENT</span>{view && <StatusLabel status={view.tone} label={view.label} />}</div>
      <p>{banner}</p>
      {result && <div className="assessment-card-meta"><span>{words(result.astronaut_id)} · {words(result.activity_context)}</span><span>{compared} measurements compared</span></div>}
    </div></div>
    <Astronaut3D signals={signals} selected={item?.indicator ?? null} onSelect={id => onSelect(id === 'approved-warning' ? (flagged ?? item?.indicator ?? '') : id)} />
    <details className="system-help"><summary>How to read the status</summary><ul><li>✓ Green: no unusual pattern among the measurements that could be compared.</li><li>▲ Amber: a statistical difference from this astronaut's own history. Exploratory, not a medical warning.</li><li>○ Grey: not assessed (missing history, too little history, or no comparable measurement). Unknown, not normal.</li><li>Red is reserved for an approved medical rule. None exists yet.</li></ul><p>The history is synthetic (fictional crew and readings). Select a measurement below to see its evidence.</p></details>
    {result && <div className="evidence-grid">{result.evidence.map(e => { const v = evidenceView(e); return <button key={e.indicator} className={selected === e.indicator ? 'active' : ''} aria-pressed={selected === e.indicator} onClick={() => onSelect(e.indicator)}><strong>{words(e.indicator)}</strong><StatusLabel status={v.tone} label={v.label} /></button> })}</div>}
    <div className="map-bottom"><div className="visit-heading"><span>Assessed check-in</span><span className="mono">{result ? result.timestamp.replace('T', ' ').replace('+00:00', ' UTC') : '—'}</span></div><div className="timeline-hint">{result ? `${words(result.astronaut_id)} · ${words(result.activity_context)} · input: ${result.data_origin} · history: synthetic` : 'Mode 1 · synthetic history · assessed by the local backend'}</div></div></section>
}
