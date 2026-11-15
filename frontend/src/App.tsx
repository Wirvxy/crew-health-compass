import { useState } from 'react'
import Dashboard from './pages/Dashboard'
import NasaDataset from './pages/NasaDataset'
import RadiationHistory from './pages/RadiationHistory'
import PageHeader from './components/PageHeader'
import Sidebar, { HOME_PAGE } from './components/Sidebar'
import type { Page } from './components/Sidebar'
export default function App() {
  const [page, setPage] = useState<Page>(HOME_PAGE) // Daily check-in: first in the sidebar, and where the logo links
  function go(next: Page) { setPage(next); window.scrollTo({ top: 0 }) }
  // Every workspace stays mounted (only hidden), so check-in drafts, the 3D model and loaded data survive page changes.
  return <div className="app-shell" data-page={page}><a href="#page-content" className="sr-only skip-link">Skip to page content</a><Sidebar page={page} onPage={go}/>
    <main id="page-content" className="app-main" tabIndex={-1}><PageHeader key={page} page={page}/><div hidden={page !== 'checkin' && page !== 'body'}><Dashboard section={page === 'checkin' || page === 'body' ? page : null} onShowBody={() => go('body')}/></div><div hidden={page !== 'nasa'}><NasaDataset/></div><div hidden={page !== 'environment'}><RadiationHistory active={page === 'environment'}/></div></main></div>
}
