import { useRef, useState } from 'react'
import type { CheckIn, CrewDraft, DailyDraft, DailyField } from '../types/assessment'
export const emptyDraft = (): CrewDraft => ({ values: { heart: '', systolic: '', diastolic: '', temperature: '', sleep: '', mood: '' }, simulated: false })
interface Props { crew: string; crews: string[]; draft: CrewDraft; submissions: Record<string, CheckIn>; onChange: (draft: CrewDraft) => void; onExample: () => void; onSubmit: (values: DailyDraft) => void }
export default function DailyCheckIn({ crew, crews, draft, submissions, onChange, onExample, onSubmit }: Props) {
  const [errors, setErrors] = useState<Partial<Record<DailyField, string>>>({}), form = useRef<HTMLFormElement>(null)
  function change(field: DailyField, value: string) { setErrors(e => ({ ...e, [field]: undefined })); onChange({ ...draft, values: { ...draft.values, [field]: value } }) }
  function submit(e: React.FormEvent) {
    e.preventDefault(); const v = draft.values, next: typeof errors = {}
    for (const f of ['heart', 'systolic', 'diastolic', 'temperature'] as const) if (!v[f] || !Number.isFinite(+v[f]) || +v[f] <= 0) next[f] = 'Enter a positive numeric value.'
    for (const f of ['heart', 'systolic', 'diastolic'] as const) if (!next[f] && !Number.isInteger(+v[f])) next[f] = 'Use a whole number.'
    if (!next.systolic && !next.diastolic && +v.systolic <= +v.diastolic) next.systolic = 'Systolic must be greater than diastolic.'
    if (v.sleep === '' || !Number.isFinite(+v.sleep) || +v.sleep < 0 || +v.sleep > 24) next.sleep = 'Enter hours from 0 to 24.'
    if (!v.mood) next.mood = 'Choose a mood.'
    setErrors(next)
    const first = Object.keys(next)[0]; if (first) { form.current?.querySelector<HTMLInputElement>(`#${first}`)?.focus(); return }
    onSubmit(v)
  }
  const submitted = submissions[crew], checked = crews.filter(c => submissions[c] && new Date(submissions[c].timestamp).toDateString() === new Date().toDateString())
  function field(id: DailyField, label: string, unit: string, placeholder: string) {
    return <div className="field"><label className="field-label" htmlFor={id}><span>{label}</span><span className="unit">{unit}</span></label><input id={id} name={id} type="number" step={['heart'].includes(id) ? '1' : 'any'} inputMode={id === 'heart' ? 'numeric' : 'decimal'} placeholder={placeholder} value={draft.values[id]} onChange={e => change(id, e.target.value)} aria-invalid={!!errors[id]} aria-describedby={`${id}-error`} required /><p id={`${id}-error`} className="error">{errors[id]}</p></div>
  }
  return <section className="panel checkin-panel" aria-labelledby="daily-checkin"><div className="panel-content"><div className="panel-intro"><div><p className="eyebrow">01 / HOW AM I TODAY?</p><h2 id="daily-checkin">Daily check-in</h2></div><span className="zone-number">TODAY</span></div><p className="description">Your daily observations, in one place. Recorded separately from the historical assay visits.</p><div className="form-heading"><span id="entry-provenance">{draft.simulated ? 'SIMULATED EXAMPLE' : 'Manual entry'}</span><button id="fill-demo" className="text-button" onClick={() => { setErrors({}); onExample() }}>{draft.simulated ? 'Clear simulated example ×' : 'Fill simulated example ↗'}</button></div>
    <form id="checkin" ref={form} noValidate onSubmit={submit}><div className="fields">{field('heart', 'Heart rate', 'bpm', 'e.g. bpm')}
      <div className="field bp"><div className="field-label" id="bp-label"><span>Blood pressure</span><span className="unit">mmHg</span></div><div className="bp-row" role="group" aria-labelledby="bp-label">{(['systolic', 'diastolic'] as const).map((id, i) => <div className="bp-input" key={id}>{i === 1 && <span className="bp-divider" aria-hidden="true">/</span>}<input id={id} name={id} type="number" inputMode="numeric" step="1" placeholder={i === 0 ? 'Systolic' : 'Diastolic'} aria-label={`${id} blood pressure in mmHg`} value={draft.values[id]} onChange={e => change(id, e.target.value)} aria-invalid={!!errors[id]} aria-describedby="bp-error" required /></div>)}</div><p className="error" id="bp-error">{errors.systolic || errors.diastolic}</p></div>
      {field('temperature', 'Body temperature', '°C', 'Degrees Celsius')}{field('sleep', 'Sleep duration', 'hours / 24h', 'Hours slept')}
      <div className="field"><label className="field-label" htmlFor="mood"><span>How are you feeling?</span><span className="unit">self-reported</span></label><select id="mood" value={draft.values.mood} onChange={e => change('mood', e.target.value)} aria-describedby="mood-error" aria-invalid={!!errors.mood} required><option value="">Choose your mood</option>{['Low', 'Fair', 'Good', 'Great'].map(m => <option key={m}>{m}</option>)}</select><p className="error" id="mood-error">{errors.mood}</p></div>
    </div><div className="checkin-meta"><div className="micro" id="crew-pending">{crews.length - checked.length} crew still need to check in today</div><div className="crew-checks">{crews.map(c => <span className={`crew-chip ${checked.includes(c) ? 'done' : ''}`} key={c}>{checked.includes(c) ? '✓' : '○'} {c}</span>)}</div></div><button className="primary submit" type="submit">Submit daily check-in <span aria-hidden="true">→</span></button><div className="submission" id="last-submitted" role="status">{submitted ? `Last submitted: ${new Date(submitted.timestamp).toLocaleString()} · ${submitted.provenance === 'simulated' ? 'SIMULATED' : 'User-entered'}` : 'Last submitted: not yet in this session.'}</div></form>
    <div className="checkin-foot">Local session only. No measurements leave this device.<br />Saving a check-in does not run a clinical assessment.</div></div></section>
}
