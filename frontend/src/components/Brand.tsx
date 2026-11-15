import type { MouseEvent } from 'react'
import logoUrl from '../assets/brand/crew-health-compass-logo.png'

/**
 * The logo, as a link. Signed in, a normal click opens Daily check-in in place (drafts kept); signed out, the link
 * reloads the start page. The PNG keeps wide transparent margins, so the frame shows only its visible area (CSS).
 */
export default function Brand({ label, onHome }: { label: string; onHome?: () => void }) {
  function click(e: MouseEvent<HTMLAnchorElement>) {
    if (!onHome || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return
    e.preventDefault(); onHome()
  }
  return <a className="brand-link" href="./" aria-label={`Crew Health Compass: ${label}`} onClick={click}>
    <span className="brand-logo-frame"><img src={logoUrl} alt="" width={2172} height={724} decoding="async" /></span>
  </a>
}
