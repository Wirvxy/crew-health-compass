import { useCallback, useEffect, useRef, useState } from 'react'
import Dashboard from './pages/Dashboard'
import NasaDataset from './pages/NasaDataset'
import ProfilePicker from './pages/ProfilePicker'
import RadiationHistory from './pages/RadiationHistory'
import PageHeader from './components/PageHeader'
import Sidebar, { HOME_PAGE } from './components/Sidebar'
import type { Page } from './components/Sidebar'
import { announceSessionChange, currentProfile, endSession, onSessionChange } from './services/session'
import type { Profile } from './services/session'

type Auth = { status: 'checking' } | { status: 'out'; notice: string; signingOut?: boolean } | { status: 'in'; profile: Profile; generation: number; chosen?: boolean }
const ENDED = 'Your session ended, or another profile was opened in this browser. Choose a profile to continue.'

/** One profile's workspace. The app gives every session a new one (a new React key), so no state or late answer carries over. */
function Workspace({ profile, chosen, onSignOut }: { profile: Profile; chosen: boolean; onSignOut: () => void }) {
  const [page, setPage] = useState<Page>(HOME_PAGE) // every session starts on Daily check-in
  const main = useRef<HTMLElement>(null)
  // Just chosen on the start page: move keyboard focus into the workspace. A restored session (reload) starts at the top.
  useEffect(() => { if (chosen) main.current?.focus() }, [chosen])
  useEffect(() => { document.title = `${profile.name} · Crew Health Compass`; return () => { document.title = 'Crew Health Compass' } }, [profile.name])
  function go(next: Page) { setPage(next); window.scrollTo({ top: 0 }) }
  // Pages stay mounted (only hidden) while the session lasts, so drafts, the 3D model and loaded data survive page changes.
  return <div className="app-shell" data-page={page}><a href="#page-content" className="sr-only skip-link">Skip to page content</a><Sidebar page={page} profile={profile} onPage={go} onSignOut={onSignOut}/>
    <main ref={main} id="page-content" className="app-main" tabIndex={-1}><PageHeader key={page} page={page}/><div hidden={page !== 'checkin' && page !== 'body'}><Dashboard profile={profile} section={page === 'checkin' || page === 'body' ? page : null} onShowBody={() => go('body')}/></div><div hidden={page !== 'nasa'}><NasaDataset/></div><div hidden={page !== 'environment'}><RadiationHistory active={page === 'environment'}/></div></main></div>
}

export default function App() {
  const [auth, setAuth] = useState<Auth>({ status: 'checking' })
  // hadSession: a workspace was open, so "your session ended" is news. A first visit or a re-check while signed out stays quiet.
  const generation = useRef(0), latestCheck = useRef(0), signingOut = useRef(false), hadSession = useRef(false)
  /** Ask the backend whose session this browser holds. Only the newest check may change the screen. */
  const revalidate = useCallback(async (notice: string) => {
    if (signingOut.current) return // logging out decides the screen until the backend has answered
    const id = ++latestCheck.current
    try {
      const profile = await currentProfile()
      if (id !== latestCheck.current) return
      if (!profile) {
        const ended = hadSession.current; hadSession.current = false
        setAuth(prev => prev.status === 'out' ? prev : { status: 'out', notice: ended ? notice : '' })
        return
      }
      hadSession.current = true
      setAuth(prev => prev.status === 'in' && prev.profile.astronaut_id === profile.astronaut_id ? prev
        : { status: 'in', profile, generation: ++generation.current })
    } catch (e) {
      if (id !== latestCheck.current) return
      // Backend unreachable: an open workspace stays (its requests show the error); otherwise show the start page.
      setAuth(prev => prev.status === 'in' ? prev : { status: 'out', notice: e instanceof Error ? e.message : 'The session could not be checked.' })
    }
  }, [])
  useEffect(() => {
    revalidate('')
    const hide = () => setAuth(prev => prev.status === 'in' ? { status: 'checking' } : prev)
    // Another tab logged out or opened a profile, or a request found the session gone: drop the workspace first, then check.
    const off = onSessionChange(() => { hide(); revalidate(ENDED) })
    const onVisible = () => { if (document.visibilityState === 'visible') revalidate(ENDED) }
    const onFocus = () => revalidate(ENDED)
    // Back or Forward can restore a whole page from the browser's memory: check it before showing personal data again.
    const onPageShow = (e: PageTransitionEvent) => { if (e.persisted) { hide(); revalidate(ENDED) } }
    document.addEventListener('visibilitychange', onVisible); window.addEventListener('focus', onFocus); window.addEventListener('pageshow', onPageShow)
    return () => { off(); document.removeEventListener('visibilitychange', onVisible); window.removeEventListener('focus', onFocus); window.removeEventListener('pageshow', onPageShow) }
  }, [revalidate])

  async function signOut() {
    latestCheck.current++ // a check still running must not reopen the workspace
    // Personal data leaves the screen before the request is sent. The profiles wait until the backend has ended the
    // session, so its cookie-clearing answer cannot arrive after, and remove, a newly opened session's cookie.
    signingOut.current = true; hadSession.current = false
    setAuth({ status: 'out', notice: '', signingOut: true })
    try { await endSession(); announceSessionChange(); setAuth({ status: 'out', notice: '' }) }
    catch (e) { setAuth({ status: 'out', notice: `Logged out on this screen, but the backend could not end the session (${e instanceof Error ? e.message : 'no answer'}). It expires within 12 hours.` }) }
    finally { signingOut.current = false }
  }
  function opened(profile: Profile) {
    latestCheck.current++; hadSession.current = true
    setAuth({ status: 'in', profile, generation: ++generation.current, chosen: true })
    announceSessionChange() // other tabs drop their workspace and check again
  }

  if (auth.status === 'checking') return <main className="profile-picker" id="page-content"><p className="picker-lead" role="status">Checking your session…</p></main>
  if (auth.status === 'out') return <ProfilePicker notice={auth.notice} busy={!!auth.signingOut} onOpen={opened} />
  return <Workspace key={auth.generation} profile={auth.profile} chosen={!!auth.chosen} onSignOut={signOut} />
}
