import { useMemo } from 'react'
import Astronaut3D from './Astronaut3D'
import type { BodyMarker } from './Astronaut3D'
import StatusLabel from './StatusLabel'
import { STATUS_VIEW, words } from '../services/monitoring'
import type { Evidence, MonitoringResult } from '../services/monitoring'
interface Props { result: MonitoringResult | null; selected: string | null; onSelect: (indicator: string) => void }
/** Display only: each evidence item's own status from the backend. */
export const evidenceView = (item: Evidence) => STATUS_VIEW[item.statistics?.status ?? 'insufficient_data']
export default function BodyMap({ result, selected, onSelect }: Props) {
  const view = result ? STATUS_VIEW[result.overall_status] : null
  // A marker is drawn only where the backend returned body_marker; null means no location.
  const marker = useMemo<BodyMarker | null>(() => result?.body_marker && view ? { location: result.body_marker, tone: view.tone } : null, [result, view])
  const flagged = result?.evidence.find(e => e.statistics?.anomaly)?.indicator ?? null
  const compared = result?.evidence.filter(e => e.statistics && e.statistics.status !== 'insufficient_data').length ?? 0
  const banner = !result ? 'No check-in assessed yet. Submit the daily check-in first.'
    : result.overall_status === 'unusual' ? `Unusual vs personal history: ${result.affected_systems.map(words).join(', ')}.${marker ? ` Select the ${marker.location} marker for the evidence.` : ''}`
    : result.overall_status === 'normal' ? `No unusual pattern among ${compared} compared measurement${compared === 1 ? '' : 's'}. Check the limitations too.`
    : result.overall_status === 'insufficient_data' ? 'Not assessed: comparable history is missing or too short. This is unknown, not normal.'
    : 'Warning from an approved rule.'
  return <section className="panel map-panel" aria-labelledby="map-title"><div className="map-header"><div className="panel-intro"><div><p className="eyebrow">02 / CREW VISUALIZATION</p><h2 id="map-title">Your astronaut, in 3D.</h2></div><span className="zone-number">360° VIEW</span></div><p className="description">The marker shows where the latest check-in differs from this astronaut's own synthetic history.</p>
    <p className="assessment-banner" role="status">{view && <StatusLabel status={view.tone} label={view.label} />}<span>{banner}</span></p></div>
    <Astronaut3D marker={marker} onMarker={() => flagged && onSelect(flagged)} />
    {marker && flagged && <div className="marker-actions"><button type="button" onClick={() => onSelect(flagged)}>View evidence for the {marker.location} marker</button></div>}
    <details className="system-help"><summary>How to read the status</summary><ul><li>✓ Green: no unusual pattern among the measurements that could be compared.</li><li>▲ Amber: a statistical difference from this astronaut's own history. Exploratory, not a medical warning.</li><li>○ Grey: not assessed (missing history, too little history, or no comparable measurement). Unknown, not normal.</li><li>Red is reserved for an approved medical rule. None exists yet.</li></ul><p>The history is synthetic (fictional crew and readings). Select a measurement below to see its evidence.</p></details>
    {result && <div className="muscle-system-grid">{result.evidence.map(e => { const v = evidenceView(e); return <button key={e.indicator} className={selected === e.indicator ? 'active' : ''} aria-pressed={selected === e.indicator} onClick={() => onSelect(e.indicator)}><strong>{words(e.indicator)}</strong><StatusLabel status={v.tone} label={v.label} /></button> })}</div>}
    <div className="map-bottom"><div className="visit-heading"><span>Assessed check-in</span><span className="mono">{result ? result.timestamp.replace('T', ' ').replace('+00:00', ' UTC') : '—'}</span></div><div className="timeline-hint">{result ? `${words(result.astronaut_id)} · ${words(result.activity_context)} · input: ${result.data_origin} · history: synthetic` : 'Mode 1 · synthetic history · assessed by the local backend'}</div></div></section>
}
