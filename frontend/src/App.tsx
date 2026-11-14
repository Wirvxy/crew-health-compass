import { useState } from 'react'
import Dashboard from './pages/Dashboard'
import NasaDataset from './pages/NasaDataset'
import PageHeader from './components/PageHeader'
import Sidebar from './components/Sidebar'
import type { Page } from './components/Sidebar'
export default function App() {
  const [page, setPage] = useState<Page>('nasa')
  function go(next: Page) { setPage(next); window.scrollTo({ top: 0 }) }
  // Both workspaces stay mounted (only hidden), so check-in drafts and the 3D model survive page changes.
  return <div className="app-shell" data-page={page}><a href="#page-content" className="sr-only skip-link">Skip to page content</a><Sidebar page={page} onPage={go}/>
    <main id="page-content" className="app-main" tabIndex={-1}><PageHeader key={page} page={page}/><div hidden={page === 'nasa'}><Dashboard section={page === 'nasa' ? null : page} onShowBody={() => go('body')}/></div><div hidden={page !== 'nasa'}><NasaDataset/></div></main></div>
}
