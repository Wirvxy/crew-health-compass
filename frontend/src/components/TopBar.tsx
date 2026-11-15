import ProfilePhoto, { hasProfilePhoto } from './ProfilePhoto'
import { profileCode } from '../services/session'
import type { Profile } from '../services/session'

// The signed-in astronaut, shown read-only: switching profile means logging out (sidebar).
// The app runs on the local backend only, so the link status is always Offline (no ground connection).
export default function TopBar({ profile, context }: { profile: Profile; context: string }) {
  return <div className="crew-bar"><div className="crew-control"><span className="avatar" aria-hidden="true">{hasProfilePhoto(profile.astronaut_id) ? <ProfilePhoto id={profile.astronaut_id} className="chip-photo" /> : profileCode(profile.astronaut_id)}</span><div><span className="crew-label">Astronaut profile</span><strong className="crew-name" id="crew-name">{profile.name}</strong></div></div>
    <div className="context"><strong>{context}</strong><small>Mode 1 · check-ins assessed by the local backend</small></div><span className="link"><span className="link-dot" />Offline</span>
  </div>
}
