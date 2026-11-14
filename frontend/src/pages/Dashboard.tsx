import { matchesSubmittedExample } from '../services/checkin'
import { useEffect, useMemo, useReducer, useState } from 'react'
import TopBar from '../components/TopBar'
import DailyCheckIn, { emptyDraft } from '../components/DailyCheckIn'
import BodyMap from '../components/BodyMap'
import MuscleReport from '../components/MuscleReport'
import type { MuscleReportEntry } from '../components/MuscleReport'
import { MUSCLES } from '../data/muscles'
import SystemDetail from '../components/SystemDetail'
import DataNotes from '../components/DataNotes'
import { loadMockData, selectAssessment } from '../services/assessment'
import { downloadReport } from '../services/report'
import type { CheckIn, CrewDraft, DailyDraft, MockData, SystemId } from '../types/assessment'

interface LinkState { mars: boolean; linked: boolean; queue: CheckIn[]; acknowledged: number }
type LinkAction = { type: 'toggle' } | { type: 'restore' } | { type: 'queue'; record: CheckIn }
function linkReducer(s: LinkState, a: LinkAction): LinkState {
  if (a.type === 'toggle') return { ...s, mars: !s.mars, linked: false }
  if (a.type === 'restore') return { ...s, linked: true, acknowledged: s.acknowledged + s.queue.length, queue: [] }
  return { ...s, queue: [...s.queue, a.record] }
}
const stories = ['Pre-flight / L-92: review the first baseline sample.', 'Pre-flight / L-44: baseline uses all available pre-flight visits.', 'Launch context / L-3: the final pre-flight assay. No in-orbit data is inferred.', 'Return / R+1: review the post-flight response. Statuses are simulated.', 'Recovery / R+45: compare with the same personal baseline.', 'Recovery / R+82: follow the measurement without assuming full recovery.']

export default function Dashboard({ active }: { active: boolean }) {
  const [data, setData] = useState<MockData | null>(null), [error, setError] = useState(''), [retry, setRetry] = useState(0)
  const [crew, setCrew] = useState('C001'), [visit, setVisit] = useState('R+1'), [systemId, setSystem] = useState<SystemId>('cardio'), [markerId, setMarker] = useState<string | null>(null)
  const [drafts, setDrafts] = useState<Record<string, CrewDraft>>({}), [submissions, setSubmissions] = useState<Record<string, CheckIn>>({})
  const [role, setRole] = useState('surgeon'), [wall, setWall] = useState(false), [notes, setNotes] = useState(false), [story, setStory] = useState<number | null>(null), [message, setMessage] = useState('')
  const [link, dispatch] = useReducer(linkReducer, { mars: false, linked: false, queue: [], acknowledged: 0 })
  const [muscleView, setMuscleView] = useState<'front' | 'back'>('front'), [muscleId, setMuscleId] = useState<string | null>(null), [reportMode, setReportMode] = useState(false), [muscleReports, setMuscleReports] = useState<MuscleReportEntry[]>([])
  const crewReports = useMemo(() => muscleReports.filter(r => r.crew === crew), [muscleReports, crew])
  const muscle = MUSCLES.find(m => m.id === muscleId && m.view === muscleView) || null
  const draft = drafts[crew] || emptyDraft()
  useEffect(() => { const controller = new AbortController(); setError(''); loadMockData(controller.signal).then(setData).catch(e => { if (!controller.signal.aborted) setError(e instanceof Error ? e.message : 'Unable to load data.') }); return () => controller.abort() }, [retry])
  const assessment = useMemo(() => data ? selectAssessment(data, crew, visit, matchesSubmittedExample(submissions[crew], data.dailyDemo.values)) : null, [data, crew, visit, submissions])
  useEffect(() => { if (!message) return; const timer = setTimeout(() => setMessage(''), 5500); return () => clearTimeout(timer) }, [message])
  useEffect(() => { if (!link.mars || link.linked) return; const timer = setTimeout(() => { dispatch({ type: 'restore' }); setMessage('Simulated ground link restored. No data was transmitted.') }, 12 * 60 * 1000); return () => clearTimeout(timer) }, [link.mars, link.linked])
  useEffect(() => { if (story == null || !data) return; setVisit(data.timepoints[story]); setMarker(null); const timer = setTimeout(() => setStory(story < 5 ? story + 1 : null), 5000); return () => clearTimeout(timer) }, [story, data])
  // Stop the guided demo when this workspace is hidden, so its timer cannot change hidden state.
  useEffect(() => { if (!active) setStory(null) }, [active])
  useEffect(() => { if (!active) return; function key(e: KeyboardEvent) { if (e.key === 'Escape') { setStory(null); return }; if (notes || ['INPUT', 'SELECT', 'TEXTAREA', 'BUTTON', 'SUMMARY'].includes((e.target as HTMLElement).tagName)) return; if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') { e.preventDefault(); setVisit(v => data?.timepoints[Math.max(0, Math.min(5, data.timepoints.indexOf(v) + (e.key === 'ArrowRight' ? 1 : -1)))] || v); setMarker(null) }; if (e.key.toLowerCase() === 'd') setStory(s => s == null ? 0 : null) }; document.addEventListener('keydown', key); return () => document.removeEventListener('keydown', key) }, [active, data, notes])
  function updateDraft(next: CrewDraft) { setDrafts(d => ({ ...d, [crew]: next })) }
  function example() { if (!data) return; updateDraft(draft.simulated ? emptyDraft() : { simulated: true, values: Object.fromEntries(Object.entries(data.dailyDemo.values).map(([key, value]) => [key, String(value)])) as DailyDraft }); setMarker(null); setMessage(draft.simulated ? 'Synthetic example cleared.' : 'Explicit synthetic values loaded. They are not Inspiration4 measurements.') }
  function submit(values: DailyDraft) { const record: CheckIn = { astronautId: crew, values: { ...values }, provenance: draft.simulated ? 'simulated' : 'user', timestamp: new Date().toISOString() }; setSubmissions(s => ({ ...s, [crew]: record })); if (link.mars && !link.linked) { dispatch({ type: 'queue', record }); setMessage('Saved in this tab session. Added to the simulated ground queue.') } else setMessage('Saved in this tab session. Assessment pending; nothing transmitted.') }
  if (error) return <main className="page"><h1>Unable to load the prototype</h1><p>{error}</p><button onClick={() => setRetry(n => n + 1)}>Retry</button></main>
  if (!data || !assessment) return <main className="page" role="status">Loading Crew Health Compass…</main>
  const system = assessment.systems.find(s => s.id === systemId)!, marker = system.markers.find(m => m.id === markerId) || system.markers.find(m => m.id === system.defaultMarker) || null
  return <div className={`${role === 'astronaut' ? 'astronaut' : ''} ${wall ? 'wall' : ''}`}>
    <a href="#daily-checkin" className="sr-only skip-link">Skip to daily check-in</a>
    <TopBar crew={crew} crews={data.crew} context={assessment.context} link={link.mars ? link.linked ? 'Live · simulated' : 'Delayed · simulated' : 'Offline'} onCrew={c => { setCrew(c); setMarker(null); setMuscleId(null) }} />
    <main className="page"><aside className="prototype-scope" aria-label="Prototype scope"><strong>SIMULATED DATA · Frontend prototype</strong><span>System labels are provisional. Clinical rules and check-in API are pending. Historical NASA assays are shown separately.</span></aside><div className="page-title"><div><p className="eyebrow">YOUR DAILY PERSPECTIVE</p><h1>Your health,<br />in perspective.</h1><p>A moment to check in. A clearer picture of what comes next.</p></div><div className="tools">
      <select id="role" aria-label="Role view" value={role} onChange={e => setRole(e.target.value)}><option value="astronaut">Astronaut view</option><option value="surgeon">Flight Surgeon view</option></select>
      <button id="mars" aria-pressed={link.mars} onClick={() => dispatch({ type: 'toggle' })}>Mars-ready {link.mars ? 'On' : 'Off'}</button>
      <button id="demo" aria-pressed={story != null} onClick={() => setStory(s => s == null ? 0 : null)}>{story == null ? '▷ Guided demo' : 'Ⅱ Stop demo'}</button>
      <button id="export" className="surgeon-only" onClick={() => { downloadReport(assessment, submissions[crew], crewReports); setMessage('PDF downloaded locally. No data transmitted.') }}>↓ Export PDF</button>
      <button id="wall" className="quiet" aria-pressed={wall} title="Large-screen mission wall" onClick={() => setWall(w => !w)}>⛶ <span className="sr-only">Mission wall</span></button>
    </div></div><div className="link-info"><span>{matchesSubmittedExample(submissions[crew], data.dailyDemo.values) ? 'SIMULATED DAILY SERIES · Recorded assays remain available · Mock API statuses' : 'OSD-575 recorded assays · Assessment statuses: simulated API fixtures'}</span><span id="latency">{link.mars ? `SIMULATED LINK · 12 min one-way · ${link.queue.length} queued · ${link.acknowledged} acknowledged` : 'LOCAL SESSION · No ground connection · No live telemetry'}</span>{link.mars && !link.linked && <button id="restore" onClick={() => { dispatch({ type: 'restore' }); setMessage('Link return simulated. Queue acknowledged locally; no data sent.') }}>Simulate link return</button>}</div>
    <div className="four-zones"><DailyCheckIn key={crew} crew={crew} crews={data.crew} draft={draft} submissions={submissions} onChange={updateDraft} onExample={example} onSubmit={submit} />
      <BodyMap view={muscleView} onView={v => { setMuscleView(v); setMuscleId(null) }} muscle={muscle} onMuscle={m => { setMuscleId(m.id); setReportMode(true) }} reportMode={reportMode} onMode={setReportMode} reports={crewReports} systems={assessment.systems} selected={systemId} visit={visit} timepoints={data.timepoints} story={story == null ? '' : stories[story]} onSelect={id => { setSystem(id); setMarker(null); setReportMode(false) }} onVisit={v => { setVisit(v); setMarker(null) }} />
      {reportMode ? <MuscleReport key={`${crew}-${muscleId}`} crew={crew} muscle={muscle} reports={crewReports} onEvidence={() => setReportMode(false)} onSave={entry => { setMuscleReports(entries => { const previous = entries.find(r => r.crew === entry.crew && r.view === entry.view && r.muscleId === entry.muscleId); return [...entries.filter(r => r !== previous), { ...entry, id: previous?.id || entry.id }] }); setMessage('Muscle location saved in this tab session. No clinical assessment or transmission performed.') }} onRemove={id => setMuscleReports(entries => entries.filter(r => r.id !== id))} onShow={entry => { setMuscleView(entry.view); setMuscleId(entry.muscleId); setReportMode(true) }} /> : <SystemDetail crew={crew} visit={visit} system={system} marker={marker} submitted={submissions[crew]} baselineMethod={data.baselineMethod} onMarker={setMarker} onNotes={() => setNotes(true)} />}
    </div><footer><span>Research prototype, not a diagnostic device.</span><span className="mono">Cited data. Personal baselines. Explicit uncertainty.</span><button id="notes" className="text-button" onClick={() => setNotes(true)}>Data &amp; prototype notes ↗</button></footer></main>
    {notes && <DataNotes onClose={() => setNotes(false)} />}{message && <div className="toast" role="status">{message}</div>}
  </div>
}
