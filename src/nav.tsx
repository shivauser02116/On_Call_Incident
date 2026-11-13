import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'

export type Route = 'login' | 'alert' | 'investigate' | 'theories' | 'fix' | 'decision' | 'success' | 'profile' | 'frames'
export type Variant = 'default' | 'risky' | 'error' | 'menu'

// Step index in the sidebar -> screen
export const stepRoutes: Route[] = ['alert', 'investigate', 'theories', 'fix', 'decision']
export const backOf: Partial<Record<Route, Route>> = { investigate: 'alert', theories: 'investigate', fix: 'theories', decision: 'fix' }

const routes: Route[] = ['login', 'alert', 'investigate', 'theories', 'fix', 'decision', 'success', 'profile', 'frames']

function parse(hash: string): { route: Route; variant: Variant } {
  const key = hash.replace('#', '')
  if (key === 'decision-risky') return { route: 'decision', variant: 'risky' }
  if (key === 'login-error') return { route: 'login', variant: 'error' }
  if (key === 'alert-menu') return { route: 'alert', variant: 'menu' }
  return { route: (routes as string[]).includes(key) ? (key as Route) : 'login', variant: 'default' }
}

type Nav = { route: Route; variant: Variant; go: (r: Route) => void; diagnosed: boolean; setDiagnosed: (v: boolean) => void; cameFrom: Route; signOut: () => void; rejected: boolean; setRejected: (v: boolean) => void }
const Ctx = createContext<Nav | null>(null)

export function NavProvider({ children }: { children: React.ReactNode }) {
  const [loc, setLoc] = useState(() => parse(window.location.hash))
  const [diagnosed, setDiagnosed] = useState(false)
  const [rejected, setRejected] = useState(false)
  const [cameFrom, setCameFrom] = useState<Route>('alert')
  const routeRef = useRef(loc.route)
  routeRef.current = loc.route

  useEffect(() => {
    const onHash = () => setLoc(parse(window.location.hash))
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  const go = useCallback((r: Route) => {
    // Remember where Profile was opened from so its Back link can return there.
    if (r === 'profile' && routeRef.current !== 'profile') setCameFrom(routeRef.current)
    window.location.hash = r
  }, [])

  const signOut = useCallback(() => {
    setDiagnosed(false)
    window.location.hash = 'login'
  }, [])

  return <Ctx.Provider value={{ ...loc, go, diagnosed, setDiagnosed, cameFrom, signOut, rejected, setRejected }}>{children}</Ctx.Provider>
}

export function useNav() {
  const v = useContext(Ctx)
  if (!v) throw new Error('useNav must be used inside NavProvider')
  return v
}
