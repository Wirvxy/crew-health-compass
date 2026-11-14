import { useRef, useState } from 'react'
import StatusLabel from './StatusLabel'
import { CONTEXTS, MOODS, STATUS_VIEW, words } from '../services/monitoring'
import type { MonitoringResult } from '../services/monitoring'
import type { CheckIn, CrewDraft, DailyDraft, DailyField } from '../types/assessment'
export const emptyDraft = (timestamp = ''): CrewDraft => ({ values: { context: '', timestamp, heart: '', respiratory: '', systolic: '', diastolic: '', sleep: '', mood: '' }, simulated: false })
export type ExampleKind = 'typical' | 'high' | 'early'
const CONTEXT_HELP: Record<string, string> = {
  rest: 'compares heart rate and blood pressure with rest history', exercise: 'compares heart rate and blood pressure with exercise history',
  recovery: 'compares heart rate and blood pressure with post-exercise history', morning_check: 'compares heart rate with morning history',
  inflight_vitals_check: 'compares heart rate and breathing rate with vitals-check history', other: 'no comparable history: nothing is compared',
}
interface Props {
  crew: string; crews: string[]; draft: CrewDraft; submissions: Record<string, CheckIn>; historyEnd: string | null
  pending: boolean; error: string; result: MonitoringResult | null
  onChange: (draft: CrewDraft) => void; onExample: (kind: ExampleKind) => void; onSubmit: (values: DailyDraft) => void; onShowBody: () => void
}
export default function DailyCheckIn({ crew, crews, draft, submissions, historyEnd, pending, error, result, onChange, onExample, onSubmit, onShowBody }: Props) {
  const [errors, setErrors] = useState<Partial<Record<DailyField, string>>>({}), form = useRef<HTMLFormElement>(null)
  function change(field: DailyField, value: string) { setErrors(e => ({ ...e, [field]: undefined })); onChange({ ...draft, values: { ...draft.values, [field]: value } }) }
  function submit(e: React.FormEvent) {
    // Input checks only: the backend validates the contract and makes every assessment.
    e.preventDefault(); const v = draft.values, next: typeof errors = {}
    if (!v.context) next.context = 'Choose how the values were measured.'
    if (!v.timestamp) next.timestamp = 'Enter the mission date and time (UTC).'
    for (const f of ['heart', 'respiratory', 'systolic', 'diastolic'] as const) if (!v[f] || !Number.isFinite(+v[f]) || +v[f] <= 0) next[f] = 'Enter a positive numeric value.'
    if (!next.systolic && !next.diastolic && +v.systolic <= +v.diastolic) next.systolic = 'Systolic must be greater than diastolic.'
    if (v.sleep !== '' && (!Number.isFinite(+v.sleep) || +v.sleep < 0 || +v.sleep > 24)) next.sleep = 'Enter hours from 0 to 24, or leave empty.'
    setErrors(next)
    const first = Object.keys(next)[0]; if (first) { form.current?.querySelector<HTMLInputElement>(`#${first}`)?.focus(); return }
    onSubmit(v)
  }
  const submitted = submissions[crew], checked = crews.filter(c => submissions[c])
  function field(id: DailyField, label: string, unit: string, placeholder: string, optional = false) {
    return <div className="field"><label className="field-label" htmlFor={id}><span>{label}{optional && ' (optional)'}</span><span className="unit">{unit}</span></label><input id={id} name={id} type="number" step="any" inputMode="decimal" placeholder={placeholder} value={draft.values[id]} onChange={e => change(id, e.target.value)} aria-invalid={!!errors[id]} aria-describedby={`${id}-error`} required={!optional} /><p id={`${id}-error`} className="error">{errors[id]}</p></div>
  }
  const view = result ? STATUS_VIEW[result.overall_status] : null
  return <section className="panel checkin-panel" aria-labelledby="daily-checkin"><div className="panel-content"><div className="panel-intro"><div><p className="eyebrow">01 / HOW AM I TODAY?</p><h2 id="daily-checkin">Daily check-in</h2></div><span className="zone-number">MODE 1</span></div><p className="description">Compared only with this astronaut's own earlier readings, in the same activity context. The history is synthetic: fictional crew and readings.</p>
    <div className="form-heading"><span id="entry-provenance">{draft.simulated ? 'EXAMPLE VALUES · filled by the app' : 'Manual entry'}</span></div>
    <div className="example-buttons" role="group" aria-label="Fill example values">{([['typical', 'Typical day'], ['high', 'High heart rate'], ['early', 'Early mission']] as const).map(([kind, label]) => <button key={kind} type="button" className="text-button" onClick={() => { setErrors({}); onExample(kind) }}>Example: {label} ↗</button>)}</div>
    <form id="checkin" ref={form} noValidate onSubmit={submit}><div className="fields">
      <div className="field bp"><label className="field-label" htmlFor="context"><span>Activity context</span><span className="unit">how it was measured</span></label><select id="context" value={draft.values.context} onChange={e => change('context', e.target.value)} aria-describedby="context-error context-help" aria-invalid={!!errors.context} required><option value="">Choose a context</option>{CONTEXTS.map(c => <option key={c} value={c}>{words(c)}</option>)}</select><p className="unit" id="context-help">{draft.values.context ? CONTEXT_HELP[draft.values.context] : 'Rest and exercise readings are never compared with each other.'}</p><p id="context-error" className="error">{errors.context}</p></div>
      <div className="field bp"><label className="field-label" htmlFor="timestamp"><span>Mission time</span><span className="unit">UTC</span></label><input id="timestamp" type="datetime-local" step="60" value={draft.values.timestamp} onChange={e => change('timestamp', e.target.value)} aria-describedby="timestamp-error timestamp-help" aria-invalid={!!errors.timestamp} required /><p className="unit" id="timestamp-help">Synthetic mission calendar{historyEnd ? `: history ends ${historyEnd.slice(0, 10)}` : ''}. Earlier times have less history.</p><p id="timestamp-error" className="error">{errors.timestamp}</p></div>
      {field('heart', 'Heart rate', 'bpm', 'e.g. 72')}{field('respiratory', 'Respiratory rate', 'breaths/min', 'e.g. 15')}
      <div className="field bp"><div className="field-label" id="bp-label"><span>Blood pressure</span><span className="unit">mmHg</span></div><div className="bp-row" role="group" aria-labelledby="bp-label">{(['systolic', 'diastolic'] as const).map((id, i) => <div className="bp-input" key={id}>{i === 1 && <span className="bp-divider" aria-hidden="true">/</span>}<input id={id} name={id} type="number" inputMode="decimal" step="any" placeholder={i === 0 ? 'Systolic' : 'Diastolic'} aria-label={`${id} blood pressure in mmHg`} value={draft.values[id]} onChange={e => change(id, e.target.value)} aria-invalid={!!errors[id]} aria-describedby="bp-error" required /></div>)}</div><p className="error" id="bp-error">{errors.systolic || errors.diastolic}</p></div>
      {field('sleep', 'Sleep duration', 'hours', 'Hours slept', true)}
      <div className="field"><label className="field-label" htmlFor="mood"><span>How are you feeling? (optional)</span><span className="unit">self-reported</span></label><select id="mood" value={draft.values.mood} onChange={e => change('mood', e.target.value)}><option value="">Not answered</option>{MOODS.map(m => <option key={m} value={m}>{m[0].toUpperCase() + m.slice(1)}</option>)}</select></div>
    </div><div className="checkin-meta"><div className="micro" id="crew-pending">{crews.length - checked.length} crew without a check-in this session</div><div className="crew-checks">{crews.map(c => <span className={`crew-chip ${checked.includes(c) ? 'done' : ''}`} key={c}>{checked.includes(c) ? '✓' : '○'} {words(c)}</span>)}</div></div><button className="primary submit" type="submit" disabled={pending}>{pending ? 'Assessing…' : <>Submit and assess <span aria-hidden="true">→</span></>}</button><div className="submission" id="last-submitted" role="status">{submitted ? `Last submitted: ${submitted.timestamp} · ${submitted.provenance === 'simulated' ? 'EXAMPLE VALUES' : 'User-entered'}` : 'Last submitted: not yet in this session.'}</div></form>
    {error && <p className="checkin-error" role="alert">{error}</p>}
    {result && view && <div className="result-card" aria-live="polite"><StatusLabel status={view.tone} label={view.label} /><p>{result.explanation}</p><button type="button" className="text-button" onClick={onShowBody}>See it on the astronaut →</button></div>}
    <div className="checkin-foot">Assessed by the local backend with personal robust statistics. Nothing is sent outside this computer.<br />An exploratory monitoring result, not a diagnosis.</div></div></section>
}
