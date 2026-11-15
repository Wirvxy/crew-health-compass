import StatusLabel from './StatusLabel'
import { STATUS_VIEW, words } from '../services/monitoring'
import type { StoredCheckIn } from '../services/personal'

const when = (iso: string) => `${iso.slice(0, 10)} ${iso.slice(11, 16)} UTC`

/** The signed-in astronaut's own stored check-ins, newest first (GET /api/me/checkins). */
export default function RecentCheckIns({ items, error }: { items: StoredCheckIn[] | null; error: string }) {
  return <section className="panel recent-panel" aria-labelledby="recent-title">
    <p className="eyebrow">YOUR HISTORY</p>
    <h2 id="recent-title">Recent check-ins</h2>
    {error ? <p role="alert" className="plan-error">{error}</p>
      : items === null ? <p role="status" className="plan-day">Loading your check-ins…</p>
      : items.length === 0 ? <p className="plan-day">No check-ins saved for your profile yet.</p>
      : <ol className="recent-list">{items.map(c => { const view = STATUS_VIEW[c.assessment.overall_status]; return <li key={c.id}>
          <span className="recent-when">Saved {when(c.received_at)}</span>
          <span className="recent-what">{words(c.check_in.activity_context)} · mission time {c.check_in.timestamp.slice(0, 16).replace('T', ' ')}</span>
          <StatusLabel status={view.tone} label={view.label} />
        </li> })}</ol>}
    <p className="plan-foot">Only your profile’s check-ins are listed. They are not added to your baseline: each check-in is compared with your synthetic history.</p>
  </section>
}
