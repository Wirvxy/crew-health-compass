import type { MouseEvent, ReactNode } from 'react'
import logoUrl from '../assets/brand/crew-health-compass-logo.png'

export type Page = 'nasa' | 'checkin' | 'body' | 'environment'
export const HOME_PAGE: Page = 'checkin'

// One entry per sidebar page, in sidebar order. The sidebar shows only the icon and label; the heading, and the
// SIMULATED or RECORDED badge that tells the data apart, are shown by PageHeader on every page.
export const PAGES: { id: Page; label: string; eyebrow: string; title: string; description: string; badge: string; badgeTitle: string; recorded: boolean }[] = [
  { id: 'checkin', label: 'Daily check-in', eyebrow: 'MODE 1 · MISSION HEALTH MONITOR / DAILY CHECK-IN', title: 'Your health, in perspective.', description: 'Enter today’s measurements. The local backend compares them with this astronaut’s own synthetic history.', badge: 'SIMULATED DATA', badgeTitle: 'Results compare check-ins with synthetic history (fictional crew and readings).', recorded: false },
  { id: 'body', label: 'Body & systems', eyebrow: 'MODE 1 · MISSION HEALTH MONITOR / BODY & SYSTEMS', title: 'Body & systems', description: 'See where the latest check-in differs from personal history, and the evidence behind it.', badge: 'SIMULATED DATA', badgeTitle: 'Results compare check-ins with synthetic history (fictional crew and readings).', recorded: false },
  { id: 'nasa', label: 'NASA lab data', eyebrow: 'MODE 2 · NASA BIOLOGICAL PASSPORT', title: 'NASA laboratory history', description: 'Real NASA OSD-575 research data: each astronaut’s postflight results compared with their own preflight average. Descriptive, not a diagnostic system.', badge: 'RECORDED DATA · OSD-575', badgeTitle: 'Recorded laboratory values from the NASA OSD-575 study.', recorded: true },
  { id: 'environment', label: 'Mission Environment', eyebrow: 'MISSION ENVIRONMENT · MARS RADIATION HISTORY', title: 'Mars Radiation History', description: 'Explore historical NASA Curiosity radiation measurements on the Martian surface.', badge: 'RECORDED DATA · CURIOSITY RAD', badgeTitle: 'Historical measurements by NASA Curiosity’s Radiation Assessment Detector on Mars.', recorded: true },
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
  // The logo is a real link (it also works with a new tab), but a normal click switches page in place, keeping drafts and results.
  function home(e: MouseEvent<HTMLAnchorElement>) {
    if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return
    e.preventDefault(); onPage(HOME_PAGE)
  }
  return <nav className="sidebar" aria-label="Pages">
    <a className="brand-link" href="./" onClick={home}>
      <span className="brand-logo-frame"><img src={logoUrl} alt="Crew Health Compass" width={2172} height={724} decoding="async" /></span>
      <span className="sr-only">: go to Daily check-in</span>
    </a>
    <ul className="sidebar-links">{PAGES.map(p => <li key={p.id}><button data-page={p.id} aria-current={p.id === page ? 'page' : undefined} onClick={() => onPage(p.id)}><span className="nav-icon"><PageIcon page={p.id}/></span><span className="nav-text"><strong>{p.label}</strong></span></button></li>)}</ul>
    <p className="sidebar-note">Research prototype, not a diagnostic device.</p>
  </nav>
}
