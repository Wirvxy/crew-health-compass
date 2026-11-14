import { useState } from 'react'
import type { FormEvent } from 'react'
import type { MuscleRegion } from '../data/muscles'

export interface MuscleReportEntry {
  id: string; crew: string; muscleId: string; muscleName: string; view: 'front' | 'back'
  severity: number; kind: string; onset: string; notes: string; provenance: 'user'; timestamp: string
}
interface Props { muscle: MuscleRegion | null; crew: string; reports: MuscleReportEntry[]; onSave: (entry: MuscleReportEntry) => void; onRemove: (id: string) => void; onShow: (entry: MuscleReportEntry) => void; onEvidence: () => void }
export default function MuscleReport({ muscle, crew, reports, onSave, onRemove, onShow, onEvidence }: Props) {
  const existing = reports.find(r => r.muscleId === muscle?.id && r.view === muscle?.view)
  const [severity, setSeverity] = useState(existing ? String(existing.severity) : ''), [kind, setKind] = useState(existing?.kind || ''), [onset, setOnset] = useState(existing?.onset || ''), [notes, setNotes] = useState(existing?.notes || ''), [error, setError] = useState('')
  function save(e: FormEvent) {
    e.preventDefault()
    if (!muscle) return
    if (severity === '' || !Number.isInteger(+severity) || +severity < 0 || +severity > 10) { setError('Choose a whole-number intensity from 0 to 10.'); return }
    if (!kind || !onset) { setError('Choose a description and when it started.'); return }
    setError(''); onSave({ id: crypto.randomUUID(), crew, muscleId: muscle.id, muscleName: muscle.name, view: muscle.view, severity: +severity, kind, onset, notes, provenance: 'user', timestamp: new Date().toISOString() })
  }
  function exportReports() {
    const url = URL.createObjectURL(new Blob([JSON.stringify({ crew, provenance: 'user', reports }, null, 2)], { type: 'application/json' }))
    const link = document.createElement('a'); link.href = url; link.download = `muscle-report-${crew}.json`; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
  return <section className="panel muscle-report-panel" aria-labelledby="discomfort-title"><div className="system-detail">
    <div className="detail-title"><div><p className="eyebrow">03 / WHERE DOES IT HURT?</p><h2 id="discomfort-title">{muscle?.name || 'Report discomfort'}</h2></div></div>
    <p className="provenance">{crew} · {muscle ? `${muscle.view.toUpperCase()} VIEW · USER-REPORTED` : 'Select an illustrated muscle to begin.'}</p>
    <button className="text-button" onClick={onEvidence}>← Back to system evidence</button>
    {muscle ? <form className="muscle-form" onSubmit={save} noValidate>
      <p className="details-note">This location is selected by you, not inferred from a blood test. Entries stay in this tab session; no clinical assessment is run.</p>
      <label htmlFor="pain-intensity">Intensity / 0–10</label><input id="pain-intensity" type="number" min="0" max="10" step="1" placeholder="Choose 0–10" value={severity} onChange={e => setSeverity(e.target.value)} aria-describedby="pain-help pain-error" required />
      <p className="details-note" id="pain-help">0 = no pain · 10 = worst pain you can imagine</p>
      <label htmlFor="pain-kind">What does it feel like?</label><select id="pain-kind" value={kind} onChange={e => setKind(e.target.value)} required><option value="">Choose a description</option>{['Aching', 'Sharp', 'Burning', 'Stiffness', 'Tingling', 'Other discomfort'].map(v => <option key={v}>{v}</option>)}</select>
      <label htmlFor="pain-onset">When did it start?</label><select id="pain-onset" value={onset} onChange={e => setOnset(e.target.value)} required><option value="">Choose onset</option>{['Just now', 'Earlier today', 'Yesterday', 'More than a day ago', 'Not sure'].map(v => <option key={v}>{v}</option>)}</select>
      <label htmlFor="pain-notes">Anything else? / optional</label><textarea id="pain-notes" maxLength={1000} value={notes} onChange={e => setNotes(e.target.value)} placeholder="What makes it better or worse?" />
      <p id="pain-error" role="alert" className="error">{error}</p><button type="submit" className="primary">Save this muscle location →</button>
    </form> : <div className="empty-state">Click a muscle on the body or choose one from the searchable list. Front and back views contain separate source-defined anatomical shapes.</div>}
    <div className="info-section"><h3>{reports.length} {reports.length === 1 ? 'location' : 'locations'} recorded / {crew}</h3>
      {reports.map((r, index) => <article key={r.id} className="muscle-report-entry"><strong><span className="report-dot">{index + 1}</span> {r.muscleName}</strong><p>{r.view.toUpperCase()} · {r.severity}/10 · {r.kind}<br />{r.onset} · user-reported</p>{r.notes && <p>{r.notes}</p>}<div><button onClick={() => onShow(r)}>Show on map</button><button aria-label={`Remove report for ${r.muscleName}`} onClick={() => onRemove(r.id)}>Remove</button></div></article>)}
      {reports.length > 0 && <button className="text-button" onClick={exportReports}>Export location report / JSON ↓</button>}
    </div>
  </div></section>
}
