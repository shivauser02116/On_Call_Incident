import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'

export type Route = 'login' | 'alert' | 'investigate' | 'theories' | 'fix' | 'decision' | 'success' | 'profile'
export type Variant = 'default' | 'risky' | 'error' | 'menu'

// Step index in the sidebar -> screen
export const stepRoutes: Route[] = ['alert', 'investigate', 'theories', 'fix', 'decision']
export const backOf: Partial<Record<Route, Route>> = {
  investigate: 'alert',
  theories: 'investigate',
  fix: 'theories',
  decision: 'fix',
}

const routes: Route[] = ['login', 'alert', 'investigate', 'theories', 'fix', 'decision', 'success', 'profile']

function parse(hash: string): { route: Route; variant: Variant } {
  const key = hash.replace('#', '')
  if (key === 'decision-risky') return { route: 'decision', variant: 'risky' }
  if (key === 'login-error') return { route: 'login', variant: 'error' }
  if (key === 'alert-menu') return { route: 'alert', variant: 'menu' }
  return { route: (routes as string[]).includes(key) ? (key as Route) : 'login', variant: 'default' }
}

export interface EvidenceItem {
  description: string
  tool_call: string
  source_row?: string | null
}

export interface Hypothesis {
  rank: number
  cause: string
  confidence: number
  evidence_for: EvidenceItem[]
  evidence_against: EvidenceItem[]
}

export interface ProposedFix {
  fix_id: string
  action: string
  risk_level: number
  blast_radius: string
  rationale: string
}

export interface InvestigationResult {
  hypotheses: Hypothesis[]
  proposed_fix: ProposedFix
}

export interface RehearsalResult {
  fix_id: string
  risk_level: number
  blast_radius: string
  before_metrics?: Record<string, any>
  after_metrics?: Record<string, any>
}

export interface UserProfile {
  username: string
  role: string
  last_sign_in?: string
}

export interface PlanStep {
  step: number
  tool: string
  description: string
  status?: 'pending' | 'running' | 'completed' | 'skipped'
}

export interface TraceStep {
  index: number
  toolName: string
  arguments: Record<string, any>
  summary: string
  durationMs: number
  isMock?: boolean
}

export interface AgentTotals {
  toolCalls: number
  tokens: number
  elapsedMs: number
  isMock?: boolean
}

export interface PlanMeta {
  source: 'model' | 'standard'
  isMock?: boolean
}

export function getCsrfToken(): string {
  if (typeof document === 'undefined') return ''
  const prefix = 'csrf_token='
  const parts = document.cookie.split(';')
  for (let i = 0; i < parts.length; i++) {
    const part = parts[i].trim()
    if (part.startsWith(prefix)) {
      return decodeURIComponent(part.substring(prefix.length))
    }
  }
  return ''
}

type Nav = {
  route: Route
  variant: Variant
  go: (r: Route) => void
  diagnosed: boolean
  setDiagnosed: (v: boolean) => void
  cameFrom: Route
  signOut: () => void
  selectedScenario: string
  setSelectedScenario: (s: string) => void
  investigationId: number | null
  setInvestigationId: (id: number | null) => void
  investigationResult: InvestigationResult | null
  setInvestigationResult: (res: InvestigationResult | null) => void
  rehearsalResult: RehearsalResult | null
  setRehearsalResult: (res: RehearsalResult | null) => void
  currentUser: UserProfile | null
  setCurrentUser: (u: UserProfile | null) => void
  agentPlan: PlanStep[]
  setAgentPlan: React.Dispatch<React.SetStateAction<PlanStep[]>>
  agentPlanMeta: PlanMeta
  setAgentPlanMeta: React.Dispatch<React.SetStateAction<PlanMeta>>
  replanReason: string | null
  setReplanReason: React.Dispatch<React.SetStateAction<string | null>>
  agentTrace: TraceStep[]
  setAgentTrace: React.Dispatch<React.SetStateAction<TraceStep[]>>
  agentTotals: AgentTotals | null
  setAgentTotals: React.Dispatch<React.SetStateAction<AgentTotals | null>>
}

const Ctx = createContext<Nav | null>(null)

export function NavProvider({ children }: { children: React.ReactNode }) {
  const [loc, setLoc] = useState(() => parse(window.location.hash))
  const [diagnosed, setDiagnosed] = useState(false)
  const [cameFrom, setCameFrom] = useState<Route>('alert')
  const [selectedScenario, setSelectedScenario] = useState<string>('bad_deploy_slow_queries')
  const [investigationId, setInvestigationId] = useState<number | null>(null)
  const [investigationResult, setInvestigationResult] = useState<InvestigationResult | null>(null)
  const [rehearsalResult, setRehearsalResult] = useState<RehearsalResult | null>(null)
  const [currentUser, setCurrentUser] = useState<UserProfile | null>(null)
  const [agentPlan, setAgentPlan] = useState<PlanStep[]>([])
  const [agentPlanMeta, setAgentPlanMeta] = useState<PlanMeta>({ source: 'standard', isMock: true })
  const [replanReason, setReplanReason] = useState<string | null>(null)
  const [agentTrace, setAgentTrace] = useState<TraceStep[]>([])
  const [agentTotals, setAgentTotals] = useState<AgentTotals | null>(null)

  const routeRef = useRef(loc.route)
  routeRef.current = loc.route

  useEffect(() => {
    const onHash = () => setLoc(parse(window.location.hash))
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  // On initial mount, fetch current user info if session exists
  useEffect(() => {
    fetch('/api/me', { credentials: 'same-origin' })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data && data.username) {
          setCurrentUser(data)
        }
      })
      .catch(() => {
        // api/me might not exist yet in Phase 2
      })
  }, [])

  const go = useCallback((r: Route) => {
    if (r === 'profile' && routeRef.current !== 'profile') setCameFrom(routeRef.current)
    window.location.hash = r
  }, [])

  const signOut = useCallback(async () => {
    try {
      await fetch('/logout', {
        method: 'POST',
        credentials: 'same-origin',
      })
    } catch {
      // Ignore network errors on logout
    }
    setDiagnosed(false)
    setInvestigationId(null)
    setInvestigationResult(null)
    setRehearsalResult(null)
    setCurrentUser(null)
    setAgentPlan([])
    setReplanReason(null)
    setAgentTrace([])
    setAgentTotals(null)
    window.location.hash = 'login'
  }, [])

  return (
    <Ctx.Provider
      value={{
        ...loc,
        go,
        diagnosed,
        setDiagnosed,
        cameFrom,
        signOut,
        selectedScenario,
        setSelectedScenario,
        investigationId,
        setInvestigationId,
        investigationResult,
        setInvestigationResult,
        rehearsalResult,
        setRehearsalResult,
        currentUser,
        setCurrentUser,
        agentPlan,
        setAgentPlan,
        agentPlanMeta,
        setAgentPlanMeta,
        replanReason,
        setReplanReason,
        agentTrace,
        setAgentTrace,
        agentTotals,
        setAgentTotals,
      }}
    >
      {children}
    </Ctx.Provider>
  )
}

export function useNav() {
  const v = useContext(Ctx)
  if (!v) throw new Error('useNav must be used inside NavProvider')
  return v
}
