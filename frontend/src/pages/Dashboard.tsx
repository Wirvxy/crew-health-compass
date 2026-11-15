import { useEffect, useMemo, useRef, useState } from 'react'
import TopBar from '../components/TopBar'
import DailyCheckIn, { emptyDraft } from '../components/DailyCheckIn'
import type { ExampleKind } from '../components/DailyCheckIn'
import PlanForToday from '../components/PlanForToday'
import RecentCheckIns from '../components/RecentCheckIns'
import BodyMap from '../components/BodyMap'
import MonitoringDetail from '../components/MonitoringDetail'
import DataNotes from '../components/DataNotes'
import { assessCheckIn, monitoringAstronauts, words } from '../services/monitoring'
import type { ActivityContext, CheckInRequest, MonitoringAstronauts, MonitoringResult } from '../services/monitoring'
import { myCheckIns } from '../services/personal'
import type { StoredCheckIn } from '../services/personal'
import { downloadMonitoringReport } from '../services/report'
import { SessionChanged } from '../services/session'
import type { Profile } from '../services/session'
import type { CheckIn, CrewDraft, DailyDraft } from '../types/assessment'

// Demo inputs tuned to the commander's rest history (see docs/examples/mode1). Only the backend decides the result.
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
const failure = (e: unknown, fallback: string) => e instanceof Error ? e.message : fallback

/** One astronaut's personal workspace. The app mounts a fresh one for every profile session, so no state carries over. */
export default function Dashboard({ profile, section, onShowBody }: { profile: Profile; section: 'checkin' | 'body' | null; onShowBody: () => void }) {
  const crew = profile.astronaut_id
  const [info, setInfo] = useState<MonitoringAstronauts | null>(null), [loadError, setLoadError] = useState(''), [retry, setRetry] = useState(0)
  const [draft, setDraft] = useState<CrewDraft | null>(null), [submitted, setSubmitted] = useState<CheckIn | null>(null)
  // `example` is known only for check-ins sent from this tab; a stored check-in does not record it (still open in the contract).
  const [current, setCurrent] = useState<{ result: MonitoringResult; example: boolean | null } | null>(null)
  const [history, setHistory] = useState<StoredCheckIn[] | null>(null), [historyError, setHistoryError] = useState(''), [version, setVersion] = useState(0)
  const [pending, setPending] = useState(false), [submitError, setSubmitError] = useState('')
  const [selected, setSelected] = useState<string | null>(null), [view, setView] = useState<'detailed' | 'simple'>('detailed'), [wall, setWall] = useState(false), [notes, setNotes] = useState(false), [message, setMessage] = useState('')
  // Aborted when this workspace closes (logout or another profile), so a late answer never reaches the next screen.
  const life = useRef<AbortController | null>(null)
  useEffect(() => { const c = new AbortController(); life.current = c; return () => c.abort() }, [])
  useEffect(() => { const c = new AbortController(); setLoadError(''); monitoringAstronauts(crew, c.signal).then(setInfo).catch(e => { if (!c.signal.aborted && !(e instanceof SessionChanged)) setLoadError(failure(e, 'Unable to reach the backend.')) }); return () => c.abort() }, [crew, retry])
  // The profile's saved check-ins: the newest one is the latest result shown on Body & systems after a reload.
  useEffect(() => {
    const c = new AbortController()
    myCheckIns(crew, 5, c.signal).then(items => {
      if (c.signal.aborted) return
      setHistory(items); setHistoryError('')
      setCurrent(now => now ?? (items[0] ? { result: items[0].assessment, example: null } : null))
    }).catch(e => { if (!c.signal.aborted && !(e instanceof SessionChanged)) setHistoryError(failure(e, 'Your check-ins could not be loaded.')) })
    return () => c.abort()
  }, [crew, version])
  useEffect(() => { if (!message) return; const timer = setTimeout(() => setMessage(''), 5500); return () => clearTimeout(timer) }, [message])
  const timing = useMemo(() => info ? afterHistory(info) : { end: '', next: '' }, [info])
  const form = draft ?? emptyDraft(timing.next)
  // Editing example values turns them into a manual entry.
  function updateDraft(next: CrewDraft) { setDraft({ ...next, simulated: false }) }
  function example(kind: ExampleKind) {
    setSelected(null); setSubmitError('')
    setDraft({ values: { ...emptyDraft(timing.next).values, ...EXAMPLES[kind] }, simulated: true })
    setMessage('Example values filled (rest). Submit to assess them.')
  }
  async function submit(values: DailyDraft) {
    const signal = life.current?.signal, example = form.simulated, body = toRequest(crew, values)
    setPending(true); setSubmitError('')
    try {
      const result = await assessCheckIn(body, signal)
      if (signal?.aborted) return
      setCurrent({ result, example }); setSelected(result.evidence.find(e => e.statistics?.anomaly)?.indicator ?? null)
      setSubmitted({ astronautId: crew, values: { ...values }, provenance: example ? 'simulated' : 'user', timestamp: body.timestamp })
      setVersion(v => v + 1) // reload the saved history and today's plan
      setMessage('Assessed and saved for your profile by the local backend.')
    } catch (error) {
      if (signal?.aborted || error instanceof SessionChanged) return
      setSubmitError(failure(error, 'The assessment failed.'))
    } finally { if (!signal?.aborted) setPending(false) }
  }
  if (loadError) return <div className="page"><h2>Unable to reach the Mode 1 backend</h2><p>{loadError}</p><button onClick={() => setRetry(n => n + 1)}>Retry</button></div>
  if (!info) return <div className="page" role="status">Loading your history…</div>
  const label = current ? `${words(current.result.overall_status)}${current.example === null ? '' : current.example ? ' · example values' : ' · user-entered'}` : ''
  return <div className={`${view === 'simple' ? 'view-simple' : ''} ${wall ? 'wall' : ''}`}>
    <div className="page"><aside className="prototype-scope" aria-label="Mode 1 scope"><strong>MODE 1 · MISSION HEALTH MONITOR · SIMULATED HISTORY</strong><span>Your check-ins are compared with your own fictional crew history by the local backend. Separate from the real NASA data in Mode 2.</span></aside><div className="page-toolbar">
      <TopBar profile={profile} context={`Synthetic ISS history · ends ${timing.end.slice(0, 10)}`} /><div className="tools">
      <select id="view-density" aria-label="Display density" value={view} onChange={e => setView(e.target.value === 'simple' ? 'simple' : 'detailed')}><option value="detailed">Detailed view</option><option value="simple">Simple view</option></select>
      <button id="export" className="detailed-only" disabled={!current} onClick={() => { if (!current) return; downloadMonitoringReport(current.result, current.example); setMessage('PDF downloaded locally. No data transmitted.') }}>↓ Export PDF</button>
      <button id="wall" className="quiet" aria-pressed={wall} title="Large-screen mission wall" onClick={() => setWall(w => !w)}>⛶ <span className="sr-only">Mission wall</span></button>
    </div></div><div className="link-info"><span>{current ? `Your latest result: ${label}` : 'No check-in saved for your profile yet'}</span><span id="latency">LOCAL SESSION · No ground connection · No live telemetry</span></div>
    <div className="zones-checkin" hidden={section !== 'checkin'}><DailyCheckIn draft={form} submitted={submitted} historyEnd={timing.end || null} pending={pending} error={submitError} result={current?.result ?? null} onChange={updateDraft} onExample={example} onSubmit={submit} onShowBody={onShowBody} />
      <div className="checkin-side"><PlanForToday crew={crew} version={version} onShowBody={onShowBody} /><RecentCheckIns items={history} error={historyError} /></div></div>
    <div className="zones-body" hidden={section !== 'body'}><BodyMap result={current?.result ?? null} selected={selected} onSelect={setSelected} /><MonitoringDetail result={current?.result ?? null} selected={selected} example={!!current?.example} onSelect={setSelected} /></div>
    <footer><span>Research prototype, not a diagnostic device.</span><span className="mono">Personal baselines. Synthetic history. Explicit uncertainty.</span><button id="notes" className="text-button" onClick={() => setNotes(true)}>Data &amp; prototype notes ↗</button></footer></div>
    {notes && <DataNotes onClose={() => setNotes(false)} />}{message && <div className="toast" role="status">{message}</div>}
  </div>
}
