interface Props { crew: string; crews: string[]; context: string; onCrew: (crew: string) => void }
// Crew controls for the simulated pages. The brand is in the sidebar and the SIMULATED badge is in the shared page heading.
// The app runs on the local backend only, so the link status is always Offline (no ground connection).
export default function TopBar({ crew, crews, context, onCrew }: Props) {
  return <div className="crew-bar"><div className="crew-control"><span className="avatar">{crew.slice(-2)}</span><div><label htmlFor="crew">Astronaut profile</label><select id="crew" value={crew} onChange={e => onCrew(e.target.value)}>{crews.map(c => <option key={c}>{c}</option>)}</select></div></div>
    <div className="context"><strong>{context}</strong><small>Mode 1 · check-ins assessed by the local backend</small></div><span className="link"><span className="link-dot" />Offline</span>
  </div>
}
