import type { ReactNode } from 'react'

export type Page = 'nasa' | 'checkin' | 'body'

// One entry per sidebar page. The heading text is shown by PageHeader, so every page shares one heading layout.
export const PAGES: { id: Page; label: string; note: string; eyebrow: string; title: string; description: string; recorded: boolean }[] = [
  { id: 'nasa', label: 'NASA lab data', note: 'Recorded · OSD-575', eyebrow: 'NASA LABORATORY ARCHIVE', title: 'NASA laboratory history', description: 'Explore recorded laboratory measurements and compare each astronaut’s postflight results with their own preflight average.', recorded: true },
  { id: 'checkin', label: 'Daily check-in', note: 'Simulated prototype', eyebrow: 'DAILY CHECK-IN', title: 'Your health, in perspective.', description: 'A moment to check in. A clearer picture of what comes next.', recorded: false },
  { id: 'body', label: 'Body & systems', note: 'Simulated prototype', eyebrow: 'BODY & SYSTEMS', title: 'Body & systems', description: 'Explore the 3D astronaut, review each body system and step through the mission visits. Statuses are simulated.', recorded: false },
]

// Simple line icons drawn for this app (no icon library): a lab flask, a clipboard with a tick, and a body outline.
const ICONS: Record<Page, ReactNode> = {
  nasa: <><path d="M9 3h6M10 3v6.5L4.8 18.2A2 2 0 0 0 6.5 21h11a2 2 0 0 0 1.7-2.8L14 9.5V3"/><path d="M7.3 15h9.4"/></>,
  checkin: <><rect x="5" y="4.5" width="14" height="16.5" rx="2.5"/><path d="M9 4.5v-1a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v1M9 13l2.2 2.2 4.3-4.4"/></>,
  body: <><circle cx="12" cy="5" r="2.3"/><path d="M6 9.5c2 .8 4 1.2 6 1.2s4-.4 6-1.2M12 10.7V15M9 21l3-6 3 6"/></>,
}
export function PageIcon({ page }: { page: Page }) {
  return <svg className="page-icon" viewBox="0 0 24 24" aria-hidden="true">{ICONS[page]}</svg>
}

export default function Sidebar({ page, onPage }: { page: Page; onPage: (page: Page) => void }) {
  return <nav className="sidebar" aria-label="Pages">
    <div className="brand"><svg className="brand-logo" viewBox="0 0 44 44" aria-hidden="true"><rect x="1" y="1" width="42" height="42" rx="11" fill="none" stroke="currentColor" /><circle cx="22" cy="22" r="11" fill="none" stroke="currentColor" /><path d="m27 15-3 10-8 4 3-10z" fill="none" stroke="currentColor" /><path d="M22 5v5m0 24v5M5 22h5m24 0h5" stroke="currentColor" /></svg><div><strong>Crew Health Compass</strong><small>PERSONAL BASELINE · MISSION PERSPECTIVE</small></div></div>
    <ul className="sidebar-links">{PAGES.map(p => <li key={p.id}><button data-page={p.id} aria-current={p.id === page ? 'page' : undefined} onClick={() => onPage(p.id)}><span className="nav-icon"><PageIcon page={p.id}/></span><span className="nav-text"><strong>{p.label}</strong><small>{p.note}</small></span></button></li>)}</ul>
    <p className="sidebar-note">Research prototype, not a diagnostic device.</p>
  </nav>
}
