import type { ReactNode } from 'react'

export type Page = 'nasa' | 'checkin' | 'body' | 'environment'

// One entry per sidebar page. The heading text is shown by PageHeader, so every page shares one heading layout.
export const PAGES: { id: Page; label: string; note: string; eyebrow: string; title: string; description: string; badge: string; badgeTitle: string; recorded: boolean }[] = [
  { id: 'nasa', label: 'NASA lab data', note: 'Mode 2 · Recorded OSD-575', eyebrow: 'MODE 2 · NASA BIOLOGICAL PASSPORT', title: 'NASA laboratory history', description: 'Real NASA OSD-575 research data: each astronaut’s postflight results compared with their own preflight average. Descriptive, not a diagnostic system.', badge: 'RECORDED DATA · OSD-575', badgeTitle: 'Recorded laboratory values from the NASA OSD-575 study.', recorded: true },
  { id: 'checkin', label: 'Daily check-in', note: 'Mode 1 · Synthetic history', eyebrow: 'MODE 1 · MISSION HEALTH MONITOR / DAILY CHECK-IN', title: 'Your health, in perspective.', description: 'Enter today’s measurements. The local backend compares them with this astronaut’s own synthetic history.', badge: 'SIMULATED DATA', badgeTitle: 'Results compare check-ins with synthetic history (fictional crew and readings).', recorded: false },
  { id: 'body', label: 'Body & systems', note: 'Mode 1 · Synthetic history', eyebrow: 'MODE 1 · MISSION HEALTH MONITOR / BODY & SYSTEMS', title: 'Body & systems', description: 'See where the latest check-in differs from personal history, and the evidence behind it.', badge: 'SIMULATED DATA', badgeTitle: 'Results compare check-ins with synthetic history (fictional crew and readings).', recorded: false },
  { id: 'environment', label: 'Mission Environment', note: 'Recorded · Curiosity RAD', eyebrow: 'MISSION ENVIRONMENT · MARS RADIATION HISTORY', title: 'Mars Radiation History', description: 'Explore historical NASA Curiosity radiation measurements on the Martian surface.', badge: 'RECORDED DATA · CURIOSITY RAD', badgeTitle: 'Historical measurements by NASA Curiosity’s Radiation Assessment Detector on Mars.', recorded: true },
]

// Simple line icons drawn for this app (no icon library): a lab flask, a clipboard with a tick, a body outline and the Sun.
const ICONS: Record<Page, ReactNode> = {
  nasa: <><path d="M9 3h6M10 3v6.5L4.8 18.2A2 2 0 0 0 6.5 21h11a2 2 0 0 0 1.7-2.8L14 9.5V3"/><path d="M7.3 15h9.4"/></>,
  checkin: <><rect x="5" y="4.5" width="14" height="16.5" rx="2.5"/><path d="M9 4.5v-1a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v1M9 13l2.2 2.2 4.3-4.4"/></>,
  body: <><circle cx="12" cy="5" r="2.3"/><path d="M6 9.5c2 .8 4 1.2 6 1.2s4-.4 6-1.2M12 10.7V15M9 21l3-6 3 6"/></>,
  environment: <><circle cx="12" cy="12" r="3.6"/><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.3 5.3l2.1 2.1M16.6 16.6l2.1 2.1M5.3 18.7l2.1-2.1M16.6 7.4l2.1-2.1"/></>,
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
