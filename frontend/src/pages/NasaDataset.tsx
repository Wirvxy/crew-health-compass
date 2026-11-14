import { useEffect, useState } from 'react'
import { createDatasetService, chartNumber, DatasetApiError } from '../services/dataset'
import type { DatasetPanel } from '../services/dataset'
import type { CrewList, PanelList, History, Postflight, TrajectoryResponse, Comparison, Decimal } from '../types/dataset'
const api = createDatasetService()
const fmt = (value: Decimal, signed = false) => { const n=chartNumber(value); return n==null ? 'Unavailable' : new Intl.NumberFormat('en-US',{maximumFractionDigits:2,signDisplay:signed?'exceptZero':'auto'}).format(n) }
const words = (value: string) => value.replaceAll('_',' ')
interface Bundle { history: History; postflight: Postflight; trajectory: TrajectoryResponse; comparison: Comparison }
function HistoryChart({history, baseline, visit, visits, unit}: {
  history: History; baseline: Decimal; visit: string; visits: string[]; unit: string
}) {
  const measurements = new Map(history.measurements.map(row => [row.visit, row]))
  const points = visits.map(code => ({
    visit: code,
    value: chartNumber(measurements.get(code)?.value),
  }))
  const average = chartNumber(baseline)
  const values = points.flatMap(point => point.value === null ? [] : [point.value])
  if (!values.length) return <p>No recorded values to plot.</p>
  if (average !== null) values.push(average)
  const low = Math.min(...values), high = Math.max(...values)
  const padding = (high - low) * .15 || 1
  const min = low - padding, max = high + padding
  const x = (index: number) => 55 + index / Math.max(1, points.length - 1) * 550
  const y = (value: number) => 175 - (value - min) / (max - min) * 145

  let path = '', gap = true
  points.forEach(({ value }, index) => {
    if (value === null) { gap = true; return }
    path += `${gap ? 'M' : 'L'}${x(index)} ${y(value)} `
    gap = false
  })

  return <>
    <h3>Measurement history ({unit})</h3>
    <svg className="nasa-chart" viewBox="0 0 660 215" role="img" aria-label={`Recorded values in ${unit} by scheduled visit. Missing measurements appear as gaps.`}>
      {[min, (min + max) / 2, max].map(value => <g key={value}>
        <line x1="55" x2="610" y1={y(value)} y2={y(value)} stroke="rgba(219,235,244,.18)"/>
        <text x="48" y={y(value) + 4} textAnchor="end">{new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 }).format(value)}</text>
      </g>)}
      {average !== null && <line x1="55" x2="610" y1={y(average)} y2={y(average)} stroke="#BDCFDC" strokeDasharray="5 5"/>}
      <path d={path} fill="none" stroke="#EDF7FB" strokeWidth="2"/>
      {points.map((point, index) => <g key={point.visit}>
        <title>{point.visit} · {point.value === null ? 'No measurement' : `${fmt(String(point.value))} ${unit}`}</title>
        {point.value !== null && <circle cx={x(index)} cy={y(point.value)} r={point.visit === visit ? 5 : 3} fill="#EFF9FD"/>}
        {point.value === null && <text x={x(index)} y="182" textAnchor="middle">—</text>}
        <text x={x(index)} y="201" textAnchor="middle">{point.visit}</text>
      </g>)}
    </svg>
    <p className="nasa-muted">Solid line for recorded values, dashed line for the personal preflight average, and gaps for missing measurements. L = days before launch. R = days after return. Visits are equally spaced on the chart.</p>
  </>
}
export default function NasaDataset() {
  const [catalog,setCatalog]=useState<{crews:CrewList;panels:PanelList}|null>(null),[catalogError,setCatalogError]=useState(''),[retry,setRetry]=useState(0)
  const [crew,setCrew]=useState('C001'),[panel,setPanel]=useState<DatasetPanel>('cmp'),[biomarker,setBiomarker]=useState('glucose'),[visit,setVisit]=useState('R+1')
  const [result,setResult]=useState<{key:string;data?:Bundle;error?:string}|null>(null),key=`${crew}/${panel}/${biomarker}`
  useEffect(()=>{const c=new AbortController();setCatalogError('');Promise.all([api.astronauts(c.signal),api.panels(c.signal)]).then(([crews,panels])=>{if(!c.signal.aborted)setCatalog({crews,panels})}).catch(e=>{if(!c.signal.aborted)setCatalogError(message(e))});return()=>c.abort()},[retry])
  useEffect(()=>{if(!catalog)return;const c=new AbortController();setResult(null);const q={panel,biomarker};Promise.all([api.measurements(crew,q,c.signal),api.postflight(crew,q,c.signal),api.trajectory(crew,q,c.signal),api.comparison(q,c.signal)]).then(([history,postflight,trajectory,comparison])=>{if(!c.signal.aborted)setResult({key,data:{history,postflight,trajectory,comparison}})}).catch(e=>{if(!c.signal.aborted)setResult({key,error:message(e)})});return()=>c.abort()},[catalog,crew,panel,biomarker,retry])
  const data=result?.key===key?result.data:undefined,error=result?.key===key?result.error:undefined
  const t=data?.trajectory.trajectory,m=data?.history.measurements.find(m=>m.visit===visit),a=data?.postflight.results.find(r=>r.visit===visit)
  const visits = catalog?.crews.astronauts.find(c => c.crew_id === crew)?.visits ?? []
  const selectedPanel=catalog?.panels.panels.find(p=>p.panel===panel)
  return <div className="nasa-page">
    {catalogError?<div role="alert" className="nasa-panel"><p>{catalogError}</p><button onClick={()=>setRetry(r=>r+1)}>Retry API connection</button></div>:!catalog?<p role="status">Loading crew and biomarker catalogue…</p>:<><div className="nasa-filters"><label>Crew<select aria-label="Crew" value={crew} onChange={e=>{setCrew(e.target.value);setVisit('R+1')}}>{catalog.crews.astronauts.map(c=><option key={c.crew_id}>{c.crew_id}</option>)}</select></label><label>Assay panel<select aria-label="Assay panel" value={panel} onChange={e=>{const p=catalog.panels.panels.find(p=>p.panel===e.target.value)!;setPanel(p.panel);setBiomarker(p.biomarkers[0]?.biomarker||'')}}>{catalog.panels.panels.map(p=><option key={p.panel} value={p.panel}>{words(p.panel)}</option>)}</select></label><label>Biomarker<select aria-label="Biomarker" value={biomarker} onChange={e=>setBiomarker(e.target.value)}>{selectedPanel?.biomarkers.map(b=><option key={b.biomarker} value={b.biomarker}>{words(b.biomarker)} · {b.unit}</option>)}</select></label><label>Visit<select aria-label="Visit" value={visit} onChange={e=>setVisit(e.target.value)}>{visits.map(v=><option key={v}>{v}</option>)}</select></label></div>
    {error?<div role="alert" className="nasa-panel"><p>{error}</p><button onClick={()=>setRetry(r=>r+1)}>Retry dataset request</button></div>:!data||!t?<p role="status">Loading recorded measurements and comparisons…</p>:<><p className="nasa-note">{data.history.note}</p><div className="nasa-layout"><section className="nasa-panel"><p className="eyebrow">{crew} / {visit} / {words(biomarker)}</p><h2>Measurement &amp; personal baseline</h2><dl className="nasa-metrics"><div><dt>Recorded value</dt><dd data-testid="nasa-value">{m?.value == null ? 'No measurement' : fmt(m.value)} <small>{m?.unit||t.unit}</small></dd><span>{m?.value_status ?? 'No sample recorded at this visit'}</span></div><div><dt>Preflight average</dt><dd data-testid="nasa-baseline">{fmt(t.baseline_value)} <small>{t.unit}</small></dd><span>{t.baseline_status === 'insufficient_baseline' ? 'Insufficient preflight measurements' : words(t.baseline_status)} · {t.baseline_sample_count} valid samples</span></div><div><dt>Change from baseline</dt><dd data-testid="nasa-change">{a?fmt(a.absolute_change,true):'Not applicable'} <small>{a?.unit}</small></dd><span>{a?words(a.change_direction):'Postflight comparisons only'}</span></div><div><dt>Laboratory comparison</dt><dd className="nasa-description" data-testid="nasa-lab">{a?words(a.lab_comparison):'Not provided for this visit'}</dd><span>Laboratory interval: {fmt(m?.lab_ref_min??null)} – {fmt(m?.lab_ref_max??null)} {m?.unit}</span></div></dl><HistoryChart history={data.history} baseline={t.baseline_value} visit={visit} visits={visits} unit={t.unit}/>{a?.analysis_notes.map(n=><p key={n}>{n}</p>)}<details><summary>Exact measurement records &amp; sources</summary><div className="nasa-table-scroll"><table><caption>Original decimal strings, without display rounding</caption><thead><tr><th>Visit</th><th>Value</th><th>Status</th><th>Source</th></tr></thead><tbody>{visits.map(code => { const row = data.history.measurements.find(record => record.visit === code); return <tr key={code}><th scope="row">{code}</th><td>{row?.value == null ? 'No measurement' : `${row.value} ${row.unit}`}</td><td>{row?.value_status ?? 'No sample'}</td><td>{row ? `${row.source.file} · row ${row.source.row} · ${row.source.value_column}` : '—'}</td></tr> })}</tbody></table></div><p>{data.history.provenance}</p></details></section>
    <section className="nasa-panel"><p className="eyebrow">POSTFLIGHT TRAJECTORY</p><h2>{words(t.trajectory_classification)}</h2><p>{t.finding}</p><p className="nasa-note">{data.trajectory.classification_note}</p><div className="nasa-table-scroll"><table><caption>How each result moved relative to this crew member’s preflight average</caption><thead><tr><th>Visit</th><th>Value ({t.unit})</th><th>Movement</th></tr></thead><tbody>{t.visits.map(v=><tr key={v.visit}><th>{v.visit}</th><td>{fmt(v.value)}</td><td>{v.distance_movement??'No comparison'}<small className="nasa-muted"> · {v.value_status}</small></td></tr>)}</tbody></table></div>{t.evidence_limitations.map(n=><p key={n}>{n}</p>)}<p className="nasa-muted">{data.trajectory.note}</p></section></div>
    <section className="nasa-panel"><p className="eyebrow">CREW COMPARISON / {words(biomarker)}</p><h2>Four-astronaut comparison</h2><p className="nasa-note">{data.comparison.classification_note}</p><div className="nasa-crew-grid">{data.comparison.trajectories.map(c=><article key={c.crew_id}><h3>{c.crew_id}</h3><p>Average: <strong>{fmt(c.baseline_value)} {c.unit}</strong></p><p>{words(c.baseline_status)} · {c.baseline_sample_count} samples</p><p>{words(c.trajectory_classification)}</p><p>{c.finding}</p>{c.visits.map(v=><p key={v.visit}>{v.visit}: {fmt(v.value)} {c.unit} · {v.distance_movement??'No comparison'}</p>)}{c.evidence_limitations.map(n=><p key={n}>{n}</p>)}</article>)}</div><p className="nasa-muted">{data.comparison.note}</p></section><details className="nasa-panel"><summary>Complete API responses (original strings and metadata)</summary><pre>{JSON.stringify(data,null,2)}</pre></details></>}
    </>}<footer className="nasa-footer"><a href="https://osdr.nasa.gov/bio/repo/data/studies/OSD-575" target="_blank" rel="noopener noreferrer">NASA OSD-575 source study ↗</a><span>Research prototype, not a diagnostic device.</span></footer></div>
}
function message(error: unknown) { return error instanceof DatasetApiError ? `Dataset API ${error.status}: ${error.message}` : error instanceof Error && error.message.startsWith('Unexpected') ? error.message : 'Unable to load NASA laboratory data. Check that the local API is running, then retry.' }
