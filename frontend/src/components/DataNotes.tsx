import { useEffect, useRef } from 'react'
export default function DataNotes({ onClose }: { onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null)
  useEffect(() => { dialog.current?.showModal() }, [])
  return <dialog ref={dialog} id="data-notes" aria-labelledby="notes-title" onClose={onClose}><div className="dialog-heading"><span className="eyebrow">EVIDENCE / TRANSPARENCY</span><button id="close-notes" onClick={() => dialog.current?.close()} aria-label="Close data notes">✕</button></div><h2 id="notes-title">What you are looking at.</h2>
    <p>Recorded measurements come from the supplied OSD-575 transformed CMP, cardiovascular Eve, immune Eve and immune Alamar files. Baselines are each person’s median available L-92, L-44 and L-3 measurements. Missing values are not filled. Only source-provided reference intervals appear.</p>
    <p>All system statuses and early-drift hints are simulated mock-response fixtures. Green does not establish healthy organ function. Sleep &amp; Mood remains unassessed until a synthetic example is explicitly loaded. Clinical guidance awaits the team’s cited catalogue.</p>
    <p>Daily values begin blank. “Fill simulated example” loads labelled synthetic measurements and trends. Submissions remain in memory for this tab session and do not run a clinical assessment. Reloading clears drafts and submissions.</p>
    <p>Mars mode simulates a 12-minute one-way delay. Check-ins queue locally until the timer or “Simulate link return” acknowledges them. No data is transmitted. Role views change density, not access permissions.</p>
    <p>The atmospheric design adapts the supplied plant-care screenshots. The orbital horizon is decorative vector art, not mission imagery. The session checklist is not a sixth biomarker.</p>
    <p><a href="https://osdr.nasa.gov/bio/repo/data/studies/OSD-575" target="_blank" rel="noopener">NASA OSD-575 data reference ↗</a></p>
  </dialog>
}
