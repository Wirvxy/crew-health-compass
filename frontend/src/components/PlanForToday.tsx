import { useEffect, useState } from 'react'
import { doneCount, msUntilNextUtcDay, recordFor, TASK_COUNT, utcDay } from '../services/dailyPlan'
import { setManualTask, usePlanStore } from '../services/dailyPlanStore'
import { words } from '../services/monitoring'

/** Today's UTC date. It changes at 00:00 UTC while the page is open, and is checked again when the tab becomes visible. */
function useUtcDay(): string {
  const [day, setDay] = useState(() => utcDay(Date.now()))
  useEffect(() => {
    let timer = 0
    const check = () => setDay(utcDay(Date.now()))
    const schedule = () => { timer = window.setTimeout(() => { check(); schedule() }, msUntilNextUtcDay(Date.now()) + 250) }
    const onVisible = () => { if (document.visibilityState === 'visible') check() }
    schedule()
    document.addEventListener('visibilitychange', onVisible); window.addEventListener('focus', check)
    return () => { window.clearTimeout(timer); document.removeEventListener('visibilitychange', onVisible); window.removeEventListener('focus', check) }
  }, [])
  return day
}

const dayLabel = (day: string) => new Date(`${day}T00:00:00Z`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' })
const timeLabel = (iso: string) => `${iso.slice(11, 16)} UTC`

// Task texts reuse the check-in form's own wording; they are not medical guidance.
const INFO = {
  checkin: "Counts once the local backend has assessed a check-in for this astronaut today. Typing values, a form error or a failed request does not count. Each check-in is compared only with this astronaut's own earlier readings, in the same activity context.",
  sleep: 'Optional field of the check-in form. Done when an assessed check-in today included hours slept.',
  mood: 'Optional and self-reported (low, fair, good or great). Done when an assessed check-in today included it.',
  review: 'Body & systems shows which measurements were compared and the evidence behind the result. It is an exploratory monitoring result, not a diagnosis. Tick this yourself once you have looked.',
} as const
type TaskId = keyof typeof INFO

function Info({ id, title, open, onToggle }: { id: TaskId; title: string; open: boolean; onToggle: () => void }) {
  return <button type="button" className="plan-info" aria-expanded={open} aria-controls={`plan-info-${id}`} onClick={onToggle}>
    <span aria-hidden="true">i</span><span className="sr-only">About: {title}</span>
  </button>
}

export default function PlanForToday({ crew, onShowBody }: { crew: string; onShowBody: () => void }) {
  const day = useUtcDay(), store = usePlanStore(), record = recordFor(store, crew, day)
  const [open, setOpen] = useState<TaskId | null>(null)
  const done = doneCount(record), checkedIn = record.checkin !== null
  const toggle = (id: TaskId) => setOpen(o => (o === id ? null : id))
  const auto: { id: Exclude<TaskId, 'review'>; title: string; done: boolean; detail: string }[] = [
    { id: 'checkin', title: 'Complete today’s check-in', done: checkedIn, detail: record.checkin ? `Assessed at ${timeLabel(record.checkin.at)} · ${record.checkin.example ? 'example values' : 'user-entered'}` : 'Done automatically after the backend assesses a check-in' },
    { id: 'sleep', title: 'Include sleep duration', done: record.sleep, detail: record.sleep ? 'Included in an assessed check-in' : 'Optional field' },
    { id: 'mood', title: 'Include how you are feeling', done: record.mood, detail: record.mood ? 'Included in an assessed check-in' : 'Optional field' },
  ]
  return <section className="panel plan-panel" aria-labelledby="plan-title">
    <p className="eyebrow">PLAN FOR TODAY · {words(crew).toUpperCase()}</p>
    <h2 id="plan-title">Plan for today</h2>
    <p className="plan-day">{dayLabel(day)} (UTC) · resets at 00:00 UTC</p>
    <div className="plan-count"><strong id="plan-count">{done} of {TASK_COUNT} done</strong></div>
    <div className="plan-bar" role="progressbar" aria-labelledby="plan-count" aria-valuemin={0} aria-valuemax={TASK_COUNT} aria-valuenow={done}><span style={{ width: `${done / TASK_COUNT * 100}%` }} /></div>
    <ul className="plan-tasks">
      {auto.map(t => <li key={t.id} className="plan-task" data-task={t.id} data-done={t.done}>
        <div className="plan-row">
          <span className="plan-mark" aria-hidden="true">{t.done ? '✓' : ''}</span>
          <span className="plan-text"><strong><span className="sr-only">{t.done ? 'Done: ' : 'Not done: '}</span>{t.title}</strong><small>{t.detail}</small></span>
          <Info id={t.id} title={t.title} open={open === t.id} onToggle={() => toggle(t.id)} />
        </div>
        <p id={`plan-info-${t.id}`} className="plan-info-text" hidden={open !== t.id}>{INFO[t.id]}</p>
      </li>)}
      <li className="plan-task" data-task="review" data-done={record.review}>
        <div className="plan-row">
          <label className="plan-manual">
            <input type="checkbox" className="plan-check" checked={record.review} disabled={!checkedIn && !record.review} onChange={e => setManualTask(crew, day, 'review', e.target.checked)} />
            <span className="plan-text"><strong>Review today’s result</strong><small>{checkedIn || record.review ? 'Tick this yourself' : 'Available after today’s check-in'}</small></span>
          </label>
          <Info id="review" title="Review today’s result" open={open === 'review'} onToggle={() => toggle('review')} />
        </div>
        <div id="plan-info-review" className="plan-info-text" hidden={open !== 'review'}><p>{INFO.review}</p><button type="button" className="text-button" onClick={onShowBody}>Open Body &amp; systems →</button></div>
      </li>
    </ul>
    <p className="plan-foot">Kept separately for each astronaut, in this browser only. Only task progress is saved here, never readings.</p>
  </section>
}
