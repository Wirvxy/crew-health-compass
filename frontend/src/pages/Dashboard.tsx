import { useState } from 'react'

const systems = [
  { name: 'Cardiovascular', short: 'Heart & circulation', level: 'amber', value: '72', unit: 'bpm', metric: 'Resting heart rate', values: [58,59,58,61,60,64,63,66,68,67,70,72] },
  { name: 'Sleep & behavioural', short: 'Rest & wellbeing', level: 'green', value: '7.8', unit: 'hours', metric: 'Sleep duration', values: [7.2,7.8,7.5,8,7.6,7.4,7.9,8.1,7.7,8,7.6,7.8] },
  { name: 'Metabolic', short: 'Energy & nutrition', level: 'green', value: 'Pending', unit: '', metric: 'Awaiting indicator catalogue', values: [] },
  { name: 'Thermal', short: 'Body temperature', level: 'green', value: '36.7', unit: '\u00b0C', metric: 'Body temperature', values: [36.6,36.7,36.5,36.8,36.6,36.7,36.8,36.6,36.7,36.6,36.8,36.7] },
]

export default function Dashboard() {
  const [selected, setSelected] = useState(0)
  const [checkIn, setCheckIn] = useState(false)
  const [saved, setSaved] = useState(false)
  const s = systems[selected]
  const min = Math.min(...s.values) - 1
  const max = Math.max(...s.values) + 1
  const points = s.values.map((v,i) => `${32+i*42},${155-(v-min)/(max-min)*115}`).join(' ')
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#overview" aria-label="Crew Health Compass home"><span className="brand-icon">&#8599;</span><span>CREW HEALTH<br/><strong>COMPASS</strong></span></a>
        <span className="nav-caption">WORKSPACE</span>
        <nav><a className="nav-active" href="#overview"><span>&#8599;</span> Health overview</a><a href="#systems"><span>&#8599;</span> Body systems</a><a href="#trend"><span>&#8599;</span> Trends & insights</a><button onClick={() => { setCheckIn(true); setSaved(false) }}><span>&#8599;</span> Daily check-in</button></nav>
        <div className="mission-card"><span className="tiny-label">MISSION CONTEXT</span><strong>Mars transit</strong><span>Offline prototype</span><div className="orbit">&#9676;</div><small>Designed for care beyond Earth.</small></div>
        <div className="profile"><span className="avatar">01</span><div><strong>Demo astronaut</strong><small>Crew member &#183; 01</small></div></div>
      </aside>
      <main id="overview">
        <header className="topbar"><span>MISSION CONTROL <span className="slash">/</span> HEALTH OVERVIEW</span><span className="offline"><i/> Local demo</span></header>
        <div className="demo-banner"><span>&#9672; &nbsp; SIMULATED DATA</span><span>Illustrative UI scenario &#183; No live assessment</span></div>
        <section className="page-heading"><div><p className="eyebrow">YOUR DAILY PERSPECTIVE</p><h1>A clearer view of your health.</h1><p>Check in. Understand your signals. Know your next step.</p></div><button className="primary" onClick={() => { setCheckIn(true); setSaved(false) }}>+ Daily check-in</button></section>
        <section className="summary-grid" aria-label="Illustrative health metrics">
          {systems.map((system,i) => <button key={system.name} className={`metric-card ${selected===i?'selected':''}`} onClick={() => setSelected(i)}><div className="card-top"><span>{system.name}</span><span className={`status-dot ${system.level}`}/></div><div className="metric-value">{system.value} <small>{system.unit}</small></div><div className="metric-footer"><span>{system.metric}</span><span>&#8599;</span></div></button>)}
        </section>
        <div className="workspace-grid">
          <section className="panel body-panel" id="systems"><div className="panel-heading"><div><p className="eyebrow">SYSTEM OVERVIEW</p><h2>Your body, at a glance</h2></div><span className="subtle-tag">DEMO</span></div>
            <div className="body-stage"><div className="scan-ring ring-one"/><div className="scan-ring ring-two"/>
              <svg className="body-figure" viewBox="0 0 300 420" role="img" aria-label="Human body outline. Select a system using the labelled controls.">
                <defs><linearGradient id="bodyFill" x1="0" y1="0" x2="1" y2="1"><stop stopColor="#27505a" stopOpacity=".5"/><stop offset="1" stopColor="#132a38" stopOpacity=".8"/></linearGradient></defs>
                <path d="M150 21c-21 0-29 15-29 33 0 16 7 30 17 34v15l-38 14c-12 5-16 18-21 36L52 242c-4 14 10 19 16 7l40-86-5 86 12 139c1 17 20 17 22 0l13-110 13 110c2 17 21 17 22 0l12-139-5-86 40 86c6 12 20 7 16-7l-27-89c-5-18-9-31-21-36l-38-14V88c10-4 17-18 17-34 0-18-8-33-29-33Z" fill="url(#bodyFill)" stroke="#507b88" strokeWidth="1.4"/>
                <path d="M150 104v146m-40-102h80m-84 37h88m-88 36h88" fill="none" stroke="#34515e" strokeDasharray="3 5"/>
                {[[150,55],[163,150],[150,213],[113,173]].map(([cx,cy],i)=><g key={i} className={`body-hotspot ${selected===[1,0,2,3][i]?'active':''}`} role="button" tabIndex={0} aria-label={`Select ${systems[[1,0,2,3][i]].name}`} onClick={()=>setSelected([1,0,2,3][i])} onKeyDown={e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();setSelected([1,0,2,3][i])}}}><circle cx={cx} cy={cy} r="15" fill={i===1?'#e9b76c':'#68d8c5'} opacity=".12"/><circle cx={cx} cy={cy} r="5" fill={i===1?'#e9b76c':'#68d8c5'}/></g>)}
              </svg>
              <span className="body-note">ILLUSTRATIVE SYSTEM MAP</span>
            </div>
            <div className="system-controls">{systems.map((system,i)=><button key={system.name} aria-pressed={selected===i} className={selected===i?'active':''} onClick={()=>setSelected(i)}><span className={`status-dot ${system.level}`}/><span>{system.name}</span><span>&#8599;</span></button>)}</div>
            <div className="legend"><span><i className="status-dot green"/> Green</span><span><i className="status-dot amber"/> Amber</span><span><i className="status-dot red"/> Red</span><small>Preset demo statuses</small></div>
          </section>
          <section className="panel detail-panel" id="trend"><div className="panel-heading"><div><p className="eyebrow">SYSTEM DETAIL</p><h2>{s.name}</h2></div><span className={`status-label ${s.level}`}>{s.level==='amber'?'Amber':'Green'} &#183; demo</span></div>
            <p className="detail-subtitle">{s.short}</p><div className="trend-heading"><div><span>{s.metric}</span><strong>{s.value} <small>{s.unit}</small></strong></div><span className="subtle-tag">12 DEMO DAYS</span></div>
            {s.values.length ? <svg className="trend-chart" viewBox="0 0 520 195" role="img" aria-label={`${s.metric}: simulated daily values ${s.values.join(', ')} ${s.unit}`}><defs><linearGradient id="chartFill" x1="0" y1="0" x2="0" y2="1"><stop stopColor="#63d5c3" stopOpacity=".22"/><stop offset="1" stopColor="#63d5c3" stopOpacity="0"/></linearGradient></defs>{[40,95,150].map(y=><line key={y} x1="26" x2="504" y1={y} y2={y} stroke="#253344" strokeDasharray="4 5"/>)}<polygon points={`32,165 ${points} 494,165`} fill="url(#chartFill)"/><polyline points={points} fill="none" stroke="#75ddcd" strokeWidth="2.5" strokeLinejoin="round"/>{s.values.map((v,i)=><circle key={i} cx={32+i*42} cy={155-(v-min)/(max-min)*115} r="3" fill="#75ddcd"/>)}<text x="30" y="188">Day 01</text><text x="240" y="188">Day 06</text><text x="458" y="188">Day 12</text><text x="30" y="25">Range {Math.min(...s.values)}–{Math.max(...s.values)} {s.unit}</text></svg> : <div className="empty-chart">Trend available after the team confirms this indicator.</div>}
            <div className="insight"><span className="insight-icon">&#8599;</span><div><h3>{selected===0?'A changing pattern, made visible':'Every signal has a story'}</h3><p>{selected===0?'This illustrative heart-rate series rises from 58 to 72 bpm. The amber status is a preset for design review, not an engine result.':'These values and colours are illustrative fixtures for reviewing the interface.'}</p></div></div>
            <div className="next-step"><p className="eyebrow">GUIDANCE & EXPLANATION</p><h3>Awaiting the team’s health catalogue</h3><p>Cited rules, explanations and next steps will appear here when the catalogue and assessment API are connected.</p><span className="pending">&#9675; &nbsp; Sources and escalation pending</span></div>
          </section>
        </div>
        <footer><span>CREW HEALTH COMPASS</span><span>UI prototype &#183; Simulated data &#183; Not a diagnostic device</span></footer>
      </main>
      {checkIn && <div className="modal-backdrop"><section className="checkin-modal" role="dialog" aria-modal="true" aria-labelledby="checkin-title"><button className="close-modal" autoFocus onClick={()=>setCheckIn(false)} aria-label="Close check-in">&#215;</button><p className="eyebrow">DAILY CHECK-IN &#183; UI PREVIEW</p><h2 id="checkin-title">Make space for your health.</h2><p>The team is confirming indicator names, units and validation rules. The measurement form will use those contracts.</p><label>Practice note <textarea placeholder="Try the check-in interaction..." disabled={saved}/></label><button className="primary" disabled={saved} onClick={()=>setSaved(true)}>{saved?'Preview complete':'Try check-in preview'}</button><p role="status">{saved?'Interaction complete. Nothing was stored or assessed.':'Preview only. No measurements are collected.'}</p><button className="text-button" onClick={()=>setCheckIn(false)}>Back to overview &#8594;</button></section></div>}
    </div>
  )
}
