import { useState } from 'react'
import Dashboard from './pages/Dashboard'
import NasaDataset from './pages/NasaDataset'
export default function App() {
  const [view,setView]=useState<'nasa'|'demo'>('nasa')
  return <><nav className="workspace-switch" aria-label="Data workspace"><button aria-pressed={view==='nasa'} onClick={()=>setView('nasa')}>NASA laboratory data</button><button aria-pressed={view==='demo'} onClick={()=>setView('demo')}>Check-in &amp; body · simulated prototype</button></nav><div hidden={view!=='nasa'}><NasaDataset/></div><div hidden={view!=='demo'}><Dashboard active={view === 'demo'}/></div></>
}
