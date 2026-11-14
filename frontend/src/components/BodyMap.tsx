import Astronaut3D from './Astronaut3D'
import StatusLabel from './StatusLabel'
import type { MuscleRegion } from '../data/muscles'
import type { MuscleReportEntry } from './MuscleReport'
import type { SystemAssessment, SystemId } from '../types/assessment'
interface Props {
  systems: SystemAssessment[]; selected: SystemId; visit: string; timepoints: string[]; story: string
  onSelect: (id: SystemId) => void; onVisit: (visit: string) => void
  view: 'front' | 'back'; onView: (view: 'front' | 'back') => void
  muscle: MuscleRegion | null; onMuscle: (muscle: MuscleRegion) => void
  reportMode: boolean; onMode: (report: boolean) => void; reports: MuscleReportEntry[]
}
export default function BodyMap({ systems, selected, visit, timepoints, story, onSelect, onVisit }: Props) {
  return <section className="panel map-panel" aria-labelledby="map-title"><div className="map-header"><div className="panel-intro"><div><p className="eyebrow">02 / CREW VISUALIZATION</p><h2 id="map-title">Your astronaut, in 3D.</h2></div><span className="zone-number">360° VIEW</span></div><p className="description">Explore every angle. Organ effects will be connected in the next step.</p></div><Astronaut3D/><p className="muscle-map-note">Illustrative flight-suit model · No organ status is encoded on the body yet.</p><details className="system-help"><summary>How to read system status</summary><p>These labels come from simulated response fixtures, not from a clinical evaluation of your entry.</p><ul><li>✓ Normal — normal in the selected demonstration.</li><li>▲ Watch — review the fixture reason in the system panel.</li><li>● Action needed — review the fixture guidance; this is not a real clinical alert.</li><li>○ Not assessed — no assessment is available.</li></ul><p>The four system labels are provisional until scope is confirmed. Select a system card below to inspect its evidence.</p></details><div className="muscle-system-grid">{systems.map(s=><button key={s.id} data-system={s.id} className={selected===s.id?'active':''} aria-pressed={selected===s.id} onClick={()=>onSelect(s.id)}><strong>{s.name}</strong><StatusLabel status={s.status}/></button>)}</div><div className="map-bottom"><div className="visit-heading"><span>Mission visits</span><span className="mono">{visit}</span></div><div className="visit-buttons">{timepoints.map(t=><button key={t} data-visit={t} className={t===visit?'active':''} aria-pressed={t===visit} onClick={()=>onVisit(t)}>{t}</button>)}</div><div className="timeline-hint">PRE-FLIGHT → RETURN → RECOVERY<br/>Discrete samples, not continuous telemetry.</div>{story&&<div className="story" aria-live="polite">{story}</div>}</div></section>
}
