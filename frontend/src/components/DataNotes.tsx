import { useEffect, useRef } from 'react'
export default function DataNotes({ onClose }: { onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null)
  useEffect(() => { dialog.current?.showModal() }, [])
  const licence = (file: string) => `${import.meta.env.BASE_URL}licenses/${file}`
  return <dialog ref={dialog} id="data-notes" aria-labelledby="notes-title" onClose={onClose}><div className="dialog-heading"><span className="eyebrow">EVIDENCE / TRANSPARENCY</span><button id="close-notes" onClick={() => dialog.current?.close()} aria-label="Close data notes">✕</button></div><h2 id="notes-title">What you are looking at.</h2>
    <p>Mode 2 uses the OSD-575 transformed CMP, cardiovascular Eve, immune Eve and immune Alamar files. Each postflight value is compared with the same person’s preflight average (L-92, L-44 and L-3). Missing values are not filled. Only source-provided laboratory limits appear.</p>
    <p>Mode 1 statuses come from the local backend: A’s M2 statistics compare each check-in with the same astronaut’s earlier readings in the same activity context. That history is Person B’s synthetic ISS dataset, with fictional crew and readings. Green means no unusual pattern among the compared measurements; it does not establish healthy organ function. Grey means not assessed. No approved action protocols exist yet, so no treatment guidance is shown.</p>
    <p>The example buttons fill labelled demo values, which are sent as a manual check-in (the contract has no separate simulated input). Results stay in memory for this tab session. Reloading clears drafts and results.</p>
    <p>Everything runs on the local backend: no data is transmitted. “Plan for today” keeps only task progress, per astronaut, in this browser, and resets at 00:00 UTC. Role views change density, not access permissions.</p>
    <p>3D model: “Astronaut” by Javi_DaviYT (Sketchfab), CC BY 4.0 (<a href={licence('Astronaut-model-NOTICE.txt')} target="_blank" rel="noopener">notice</a>). Font: Inter, SIL Open Font License 1.1 (<a href={licence('Inter-OFL.txt')} target="_blank" rel="noopener">licence</a>). The atmospheric design adapts the supplied plant-care screenshots.</p>
    <p><a href="https://osdr.nasa.gov/bio/repo/data/studies/OSD-575" target="_blank" rel="noopener">NASA OSD-575 data reference ↗</a></p>
  </dialog>
}
