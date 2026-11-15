import { useEffect, useRef, useState } from 'react'
import Brand from '../components/Brand'
import { listProfiles, openProfile, profileCode } from '../services/session'
import type { Profile } from '../services/session'

// One accent per profile, from the app's page palette (decorative only, never a status colour).
const TONES = ['teal', 'blue', 'violet', 'peach'] as const

function Helmet() {
  return <svg className="picker-helmet" viewBox="0 0 48 48" aria-hidden="true">
    <circle cx="24" cy="20" r="13" /><path d="M14.5 19.5c0-4 4.3-6.5 9.5-6.5s9.5 2.5 9.5 6.5-4.3 6-9.5 6-9.5-2-9.5-6z" />
    <path d="M10 44c1.5-6.5 7-10 14-10s12.5 3.5 14 10" /><path d="M19 37.5h10" />
  </svg>
}

/** Start page: click a crew profile to open its personal workspace (demo access control, no passwords). */
export default function ProfilePicker({ notice, busy, onOpen }: { notice: string; busy: boolean; onOpen: (profile: Profile) => void }) {
  const [profiles, setProfiles] = useState<Profile[] | null>(null), [loadError, setLoadError] = useState(''), [retry, setRetry] = useState(0)
  const [opening, setOpening] = useState<string | null>(null), [error, setError] = useState('')
  const heading = useRef<HTMLHeadingElement>(null)
  useEffect(() => { heading.current?.focus() }, [])
  useEffect(() => {
    const c = new AbortController(); setLoadError('')
    listProfiles(c.signal).then(p => { if (!c.signal.aborted) setProfiles(p) }).catch(e => { if (!c.signal.aborted) setLoadError(e instanceof Error ? e.message : 'Crew profiles could not be loaded.') })
    return () => c.abort()
  }, [retry])
  async function choose(profile: Profile) {
    setOpening(profile.astronaut_id); setError('')
    try { onOpen(await openProfile(profile.astronaut_id)) }
    catch (e) { setError(e instanceof Error ? e.message : 'The profile could not be opened.'); setOpening(null) }
  }
  return <main className="profile-picker" id="page-content">
    <div className="picker-shell">
      <Brand label="start page" />
      <h1 ref={heading} tabIndex={-1}>Who’s checking in?</h1>
      <p className="picker-lead">Choose your crew profile to open your personal workspace. Daily check-in and Body &amp; systems are yours alone; NASA lab data and Mission Environment are shared reference data.</p>
      {notice && <p className="picker-notice" role="status">{notice}</p>}
      {busy && <p className="picker-lead" role="status">Logging out…</p>}
      {loadError ? <div className="picker-error" role="alert"><p>{loadError}</p><button type="button" onClick={() => setRetry(n => n + 1)}>Retry</button></div>
        : !profiles ? <p className="picker-lead" role="status">Loading crew profiles…</p>
        : <ul className="picker-grid" aria-label="Crew profiles">{profiles.map((p, i) => <li key={p.astronaut_id}>
            <button type="button" className="picker-card" data-profile={p.astronaut_id} data-tone={TONES[i % TONES.length]} disabled={busy || opening !== null} aria-busy={opening === p.astronaut_id} aria-label={`Open ${p.name}’s workspace`} aria-describedby="picker-note" onClick={() => choose(p)}>
              <span className="picker-avatar"><Helmet /><span className="picker-code">{profileCode(p.astronaut_id)}</span></span>
              <span className="picker-name">{p.name}</span>
              <span className="picker-state" aria-live="polite">{opening === p.astronaut_id ? 'Opening…' : ''}</span>
            </button>
          </li>)}</ul>}
      {error && <p className="picker-error" role="alert">{error}</p>}
      <p className="picker-note" id="picker-note">Local demo · simulated crew profiles. Choosing a profile is demo access control: there are no passwords, so anyone using this computer can open any profile.</p>
    </div>
  </main>
}
