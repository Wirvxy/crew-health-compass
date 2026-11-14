import { PAGES, PageIcon } from './Sidebar'
import type { Page } from './Sidebar'

// The same heading on every page. The badge says whether the page shows recorded or simulated data.
export default function PageHeader({ page }: { page: Page }) {
  const p = PAGES.find(item => item.id === page)!
  return <header className="page-title app-header"><div><p className="eyebrow"><PageIcon page={page}/>CREW HEALTH COMPASS / {p.eyebrow}</p><h1>{p.title}</h1><p>{p.description}</p></div>
    {p.recorded
      ? <span className="badge" title="Recorded laboratory values from the NASA OSD-575 study.">RECORDED DATA · OSD-575</span>
      : <span id="simulation-badge" className="badge simulated" title="Assessment statuses are simulated fixtures. Assay values are recorded data.">SIMULATED DATA</span>}
  </header>
}
