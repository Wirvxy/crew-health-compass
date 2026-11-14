import { useEffect, useRef } from 'react'
export default function DataNotes({ onClose }: { onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null)
  useEffect(() => { dialog.current?.showModal() }, [])
  return <dialog ref={dialog} id="data-notes" aria-labelledby="notes-title" onClose={onClose}><div className="dialog-heading"><span className="eyebrow">EVIDENCE / TRANSPARENCY</span><button id="close-notes" onClick={() => dialog.current?.close()} aria-label="Close data notes">✕</button></div><h2 id="notes-title">What you are looking at.</h2>
    <p>Recorded measurements come from the supplied OSD-575 transformed CMP, cardiovascular Eve, immune Eve and immune Alamar files. Baselines are each person’s median available L-92, L-44 and L-3 measurements. Missing values are not filled. Only source-provided reference intervals appear.</p>
    <p>Mode 1 statuses come from the local backend: A’s M2 statistics compare each check-in with the same astronaut’s earlier readings in the same activity context. That history is Person B’s synthetic ISS dataset, with fictional crew and readings. Green means no unusual pattern among the compared measurements; it does not establish healthy organ function. Grey means not assessed. No approved action protocols exist yet, so no treatment guidance is shown.</p>
    <p>The example buttons fill labelled demo values, which are sent as a manual check-in (the contract has no separate simulated input). Results stay in memory for this tab session. Reloading clears drafts and results.</p>
    <p>Mars mode simulates a 12-minute one-way delay. Check-ins queue locally until the timer or “Simulate link return” acknowledges them. No data is transmitted. Role views change density, not access permissions.</p>
    <p>The muscle map contains 40 front and 49 back source-defined regions, including muscle groups and some joint regions. Each rendered SVG path is also its click target. User symptom reports remain separate from assay evidence, are tagged user-reported and clear on reload.</p>
    <p>Muscle geometry: Body Muscles by Ivan Vulovic, Apache License 2.0. Adapted with new styling, accessibility and symptom reporting. <a href="https://github.com/vulovix/body-muscles" target="_blank" rel="noopener">Original source</a> · <a href={`${import.meta.env.BASE_URL}licenses/BodyMuscles-LICENSE.txt`} target="_blank" rel="noopener">Licence</a> · <a href={`${import.meta.env.BASE_URL}licenses/BodyMuscles-NOTICE.txt`} target="_blank" rel="noopener">Copyright notice</a>.</p>
    <p>The atmospheric design adapts the supplied plant-care screenshots. The orbital horizon is decorative vector art, not mission imagery. The session checklist is not a sixth biomarker.</p>
    <p><a href="https://osdr.nasa.gov/bio/repo/data/studies/OSD-575" target="_blank" rel="noopener">NASA OSD-575 data reference ↗</a></p>
  </dialog>
}
