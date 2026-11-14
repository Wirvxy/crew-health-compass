import { useEffect, useMemo, useReducer, useState } from 'react'
import TopBar from '../components/TopBar'
import DailyCheckIn, { emptyDraft } from '../components/DailyCheckIn'
import type { ExampleKind } from '../components/DailyCheckIn'
import BodyMap from '../components/BodyMap'
import MonitoringDetail from '../components/MonitoringDetail'
import DataNotes from '../components/DataNotes'
import { assessCheckIn, monitoringAstronauts, words } from '../services/monitoring'
import type { ActivityContext, CheckInRequest, MonitoringAstronauts, MonitoringResult } from '../services/monitoring'
import { downloadMonitoringReport } from '../services/report'
import type { CheckIn, CrewDraft, DailyDraft } from '../types/assessment'

interface LinkState { mars: boolean; linked: boolean; queue: CheckIn[]; acknowledged: number }
type LinkAction = { type: 'toggle' } | { type: 'restore' } | { type: 'queue'; record: CheckIn }
function linkReducer(s: LinkState, a: LinkAction): LinkState {
  if (a.type === 'toggle') return { ...s, mars: !s.mars, linked: false }
  if (a.type === 'restore') return { ...s, linked: true, acknowledged: s.acknowledged + s.queue.length, queue: [] }
  return { ...s, queue: [...s.queue, a.record] }
}
// Demo inputs for commander's rest history (see docs/examples/mode1). Only the backend decides the result.
const EXAMPLE_CREW = 'commander'
const EXAMPLES: Record<ExampleKind, Partial<DailyDraft>> = {
  typical: { context: 'rest', heart: '67', respiratory: '15', systolic: '100', diastolic: '59', sleep: '7.5', mood: 'good' },
  high: { context: 'rest', heart: '85', respiratory: '15', systolic: '100', diastolic: '59', sleep: '7.5', mood: 'good' },
  early: { context: 'rest', timestamp: '2030-01-03T13:30', heart: '67', respiratory: '15', systolic: '100', diastolic: '59', sleep: '7.5', mood: 'good' },
}
/** The request in the exact MODE1_CONTRACT.md format: decimal strings, units, UTC timestamp. */
function toRequest(crew: string, v: DailyDraft): CheckInRequest {
  const q = (value: string, unit: string) => ({ value: value.trim(), unit })
  return {
    astronaut_id: crew, timestamp: `${v.timestamp.length === 16 ? `${v.timestamp}:00` : v.timestamp}Z`, activity_context: v.context as ActivityContext, data_origin: 'user',
    indicators: { heart_rate: q(v.heart, 'bpm'), respiratory_rate: q(v.respiratory, 'breaths/min'), systolic_bp: q(v.systolic, 'mmHg'), diastolic_bp: q(v.diastolic, 'mmHg'),
      ...(v.sleep.trim() ? { sleep_duration: q(v.sleep, 'h') } : {}), ...(v.mood ? { mood: v.mood } : {}) },
  }
}
/** Default mission time: the day after the synthetic history ends, so every context has earlier readings. */
function afterHistory(info: MonitoringAstronauts) {
  const end = info.astronauts.flatMap(a => a.history.map(h => h.last)).sort().pop() ?? ''
  if (!end) return { end, next: '' }
  const day = new Date(end); day.setUTCDate(day.getUTCDate() + 1)
  return { end, next: `${day.toISOString().slice(0, 10)}T12:00` }
}

export default function Dashboard({ section, onShowBody }: { section: 'checkin' | 'body' | null; onShowBody: () => void }) {
  const [info, setInfo] = useState<MonitoringAstronauts | null>(null), [loadError, setLoadError] = useState(''), [retry, setRetry] = useState(0)
  const [crew, setCrew] = useState(EXAMPLE_CREW), [drafts, setDrafts] = useState<Record<string, CrewDraft>>({}), [submissions, setSubmissions] = useState<Record<string, CheckIn>>({})
  const [results, setResults] = useState<Record<string, { result: MonitoringResult; example: boolean }>>({}), [pending, setPending] = useState(false), [submitError, setSubmitError] = useState('')
  const [selected, setSelected] = useState<string | null>(null), [role, setRole] = useState('surgeon'), [wall, setWall] = useState(false), [notes, setNotes] = useState(false), [message, setMessage] = useState('')
  const [link, dispatch] = useReducer(linkReducer, { mars: false, linked: false, queue: [], acknowledged: 0 })
  useEffect(() => { const controller = new AbortController(); setLoadError(''); monitoringAstronauts(controller.signal).then(setInfo).catch(e => { if (!controller.signal.aborted) setLoadError(e instanceof Error ? e.message : 'Unable to reach the backend.') }); return () => controller.abort() }, [retry])
  useEffect(() => { if (!message) return; const timer = setTimeout(() => setMessage(''), 5500); return () => clearTimeout(timer) }, [message])
  useEffect(() => { if (!link.mars || link.linked) return; const timer = setTimeout(() => { dispatch({ type: 'restore' }); setMessage('Simulated ground link restored. No data was transmitted.') }, 12 * 60 * 1000); return () => clearTimeout(timer) }, [link.mars, link.linked])
  const timing = useMemo(() => info ? afterHistory(info) : { end: '', next: '' }, [info])
  const draft = drafts[crew] || emptyDraft(timing.next), current = results[crew] ?? null
  // Editing example values turns them into a manual entry.
  function updateDraft(next: CrewDraft) { setDrafts(d => ({ ...d, [crew]: { ...next, simulated: false } })) }
  function example(kind: ExampleKind) {
    setCrew(EXAMPLE_CREW); setSelected(null); setSubmitError('')
    setDrafts(d => ({ ...d, [EXAMPLE_CREW]: { values: { ...emptyDraft(timing.next).values, ...EXAMPLES[kind] }, simulated: true } }))
    setMessage('Example values filled for commander (rest). Submit to assess them.')
  }
  async function submit(values: DailyDraft) {
    const who = crew, example = draft.simulated, body = toRequest(who, values)
    setPending(true); setSubmitError('')
    try {
      const result = await assessCheckIn(body)
      setResults(r => ({ ...r, [who]: { result, example } })); setSelected(result.evidence.find(e => e.statistics?.anomaly)?.indicator ?? null)
      const record: CheckIn = { astronautId: who, values: { ...values }, provenance: example ? 'simulated' : 'user', timestamp: body.timestamp }
      setSubmissions(s => ({ ...s, [who]: record }))
      if (link.mars && !link.linked) { dispatch({ type: 'queue', record }); setMessage('Assessed locally. Added to the simulated ground queue.') } else setMessage('Assessed by the local backend.')
    } catch (error) { setSubmitError(error instanceof Error ? error.message : 'The assessment failed.') } finally { setPending(false) }
  }
  if (loadError) return <div className="page"><h2>Unable to reach the Mode 1 backend</h2><p>{loadError}</p><button onClick={() => setRetry(n => n + 1)}>Retry</button></div>
  if (!info) return <div className="page" role="status">Loading Mode 1 crew and history…</div>
  const crews = info.astronauts.map(a => a.astronaut_id)
  return <div className={`${role === 'astronaut' ? 'astronaut' : ''} ${wall ? 'wall' : ''}`}>
    <div className="page"><aside className="prototype-scope" aria-label="Mode 1 scope"><strong>MODE 1 · MISSION HEALTH MONITOR · SIMULATED HISTORY</strong><span>Check-ins are compared with fictional crew history by the local backend. Separate from the real NASA data in Mode 2.</span></aside><div className="page-toolbar">
      <TopBar crew={crew} crews={crews} context={`Synthetic ISS history · ends ${timing.end.slice(0, 10)}`} link={link.mars ? link.linked ? 'Live · simulated' : 'Delayed · simulated' : 'Offline'} onCrew={c => { setCrew(c); setSelected(null); setSubmitError('') }} /><div className="tools">
      <select id="role" aria-label="Role view" value={role} onChange={e => setRole(e.target.value)}><option value="astronaut">Astronaut view</option><option value="surgeon">Flight Surgeon view</option></select>
      <button id="mars" aria-pressed={link.mars} onClick={() => dispatch({ type: 'toggle' })}>Mars-ready {link.mars ? 'On' : 'Off'}</button>
      <button id="export" className="surgeon-only" disabled={!current} onClick={() => { if (!current) return; downloadMonitoringReport(current.result, current.example); setMessage('PDF downloaded locally. No data transmitted.') }}>↓ Export PDF</button>
      <button id="wall" className="quiet" aria-pressed={wall} title="Large-screen mission wall" onClick={() => setWall(w => !w)}>⛶ <span className="sr-only">Mission wall</span></button>
    </div></div><div className="link-info"><span>{current ? `Latest result for ${words(crew)}: ${words(current.result.overall_status)} · ${current.example ? 'example values' : 'user-entered'}` : `No check-in assessed for ${words(crew)} yet`}</span><span id="latency">{link.mars ? `SIMULATED LINK · 12 min one-way · ${link.queue.length} queued · ${link.acknowledged} acknowledged` : 'LOCAL SESSION · No ground connection · No live telemetry'}</span>{link.mars && !link.linked && <button id="restore" onClick={() => { dispatch({ type: 'restore' }); setMessage('Link return simulated. Queue acknowledged locally; no data sent.') }}>Simulate link return</button>}</div>
    <div className="zones-checkin" hidden={section !== 'checkin'}><DailyCheckIn key={crew} crew={crew} crews={crews} draft={draft} submissions={submissions} historyEnd={timing.end || null} pending={pending} error={submitError} result={current?.result ?? null} onChange={updateDraft} onExample={example} onSubmit={submit} onShowBody={onShowBody} /></div>
    <div className="zones-body" hidden={section !== 'body'}><BodyMap result={current?.result ?? null} selected={selected} onSelect={setSelected} /><MonitoringDetail result={current?.result ?? null} selected={selected} example={!!current?.example} onSelect={setSelected} /></div>
    <footer><span>Research prototype, not a diagnostic device.</span><span className="mono">Personal baselines. Synthetic history. Explicit uncertainty.</span><button id="notes" className="text-button" onClick={() => setNotes(true)}>Data &amp; prototype notes ↗</button></footer></div>
    {notes && <DataNotes onClose={() => setNotes(false)} />}{message && <div className="toast" role="status">{message}</div>}
  </div>
}
