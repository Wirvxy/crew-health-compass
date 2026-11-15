import { useEffect, useState } from 'react'
import { msUntilNextUtcDay, utcDay } from '../services/dailyPlan'
import { markReview, myPlan } from '../services/personal'
import type { Plan } from '../services/personal'
import { SessionChanged } from '../services/session'

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
  checkin: "Counts once the local backend has assessed and saved a check-in for your profile today. Typing values, a form error or a failed request does not count. Each check-in is compared only with your own earlier readings, in the same activity context.",
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

/** The signed-in astronaut's checklist. `version` changes after each saved check-in, to reload the plan. */
export default function PlanForToday({ crew, version, onShowBody }: { crew: string; version: number; onShowBody: () => void }) {
  const day = useUtcDay()
  const [state, setState] = useState<{ key: string; plan?: Plan; error?: string } | null>(null)
  const [open, setOpen] = useState<TaskId | null>(null), [saving, setSaving] = useState(false), [retry, setRetry] = useState(0)
  const [ticked, setTicked] = useState<boolean | null>(null) // shown at once while the backend saves it
  const key = `${day}/${version}/${retry}`
  useEffect(() => {
    const c = new AbortController()
    myPlan(crew, day, c.signal).then(plan => { if (!c.signal.aborted) setState({ key, plan }) })
      .catch(e => { if (!c.signal.aborted && !(e instanceof SessionChanged)) setState({ key, error: e instanceof Error ? e.message : 'The plan could not be loaded.' }) })
    return () => c.abort()
  }, [crew, day, key])
  // While a newer plan loads after a check-in, keep showing the same day's plan rather than a blank card.
  const plan = state?.plan?.day === day ? state.plan : undefined, error = state?.key === key ? state.error : undefined
  const toggle = (id: TaskId) => setOpen(o => (o === id ? null : id))
  async function tick(done: boolean) {
    setSaving(true); setTicked(done)
    try { const next = await markReview(crew, day, done); setState({ key, plan: next }) }
    catch (e) { if (!(e instanceof SessionChanged)) setState(s => ({ key, plan: s?.plan, error: e instanceof Error ? `Not saved: ${e.message}` : 'Not saved.' })) }
    finally { setSaving(false); setTicked(null) } // the saved answer (or the old state, on failure) shows again
  }

  const head = <><p className="eyebrow">PLAN FOR TODAY</p><h2 id="plan-title">Plan for today</h2><p className="plan-day">{dayLabel(day)} (UTC) · resets at 00:00 UTC</p></>
  if (!plan) return <section className="panel plan-panel" aria-labelledby="plan-title">{head}
    {error ? <div role="alert" className="plan-error"><p>{error}</p><button type="button" className="text-button" onClick={() => setRetry(n => n + 1)}>Retry</button></div> : <p role="status" className="plan-day">Loading today’s plan…</p>}
  </section>
  const t = plan.tasks, checkedIn = t.checkin.done, reviewDone = ticked ?? t.review.done
  const auto: { id: Exclude<TaskId, 'review'>; title: string; done: boolean; detail: string }[] = [
    { id: 'checkin', title: 'Complete today’s check-in', done: checkedIn, detail: t.checkin.at ? `Assessed and saved at ${timeLabel(t.checkin.at)}` : 'Done automatically after the backend assesses a check-in' },
    { id: 'sleep', title: 'Include sleep duration', done: t.sleep.done, detail: t.sleep.done ? 'Included in an assessed check-in' : 'Optional field' },
    { id: 'mood', title: 'Include how you are feeling', done: t.mood.done, detail: t.mood.done ? 'Included in an assessed check-in' : 'Optional field' },
  ]
  return <section className="panel plan-panel" aria-labelledby="plan-title">{head}
    <div className="plan-count"><strong id="plan-count">{plan.done_count} of {plan.task_count} done</strong></div>
    <div className="plan-bar" role="progressbar" aria-labelledby="plan-count" aria-valuemin={0} aria-valuemax={plan.task_count} aria-valuenow={plan.done_count}><span style={{ width: `${plan.done_count / plan.task_count * 100}%` }} /></div>
    <ul className="plan-tasks">
      {auto.map(task => <li key={task.id} className="plan-task" data-task={task.id} data-done={task.done}>
        <div className="plan-row">
          <span className="plan-mark" aria-hidden="true">{task.done ? '✓' : ''}</span>
          <span className="plan-text"><strong><span className="sr-only">{task.done ? 'Done: ' : 'Not done: '}</span>{task.title}</strong><small>{task.detail}</small></span>
          <Info id={task.id} title={task.title} open={open === task.id} onToggle={() => toggle(task.id)} />
        </div>
        <p id={`plan-info-${task.id}`} className="plan-info-text" hidden={open !== task.id}>{INFO[task.id]}</p>
      </li>)}
      <li className="plan-task" data-task="review" data-done={reviewDone}>
        <div className="plan-row">
          <label className="plan-manual">
            <input type="checkbox" className="plan-check" checked={reviewDone} disabled={saving || (!checkedIn && !t.review.done)} onChange={e => tick(e.target.checked)} />
            <span className="plan-text"><strong>Review today’s result</strong><small>{checkedIn || t.review.done ? 'Tick this yourself' : 'Available after today’s check-in'}</small></span>
          </label>
          <Info id="review" title="Review today’s result" open={open === 'review'} onToggle={() => toggle('review')} />
        </div>
        <div id="plan-info-review" className="plan-info-text" hidden={open !== 'review'}><p>{INFO.review}</p><button type="button" className="text-button" onClick={onShowBody}>Open Body &amp; systems →</button></div>
      </li>
    </ul>
    {error && <p role="alert" className="plan-error">{error}</p>}
    <p className="plan-foot">Saved on the local backend for your profile only. Other crew profiles have their own plan.</p>
  </section>
}
