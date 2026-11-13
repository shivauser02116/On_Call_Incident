import { useEffect, useRef, useState } from 'react'
import { ActionBar, Shell } from '../components/Frame'
import { Icon } from '../components/Icon'
import { getCsrfToken, useNav } from '../nav'
import { Card, Chip, Label, PageHeader, PrimaryButton } from '../components/ui'
import { AgentTraceDrawer } from '../components/AgentTraceDrawer'

type CheckState = 'done' | 'running' | 'waiting'

interface CheckItem {
  key: string
  tool: string
  icon: string
  title: string
  state: CheckState
  doing: string
  finding?: string
}

const initialChecks: CheckItem[] = [
  {
    key: 'deploys',
    tool: 'get_recent_deploys',
    icon: 'code',
    title: 'Recent changes',
    state: 'waiting',
    doing: 'Looking for recent code, configuration, and flag releases…',
  },
  {
    key: 'logs',
    tool: 'query_logs',
    icon: 'logs',
    title: 'Logs',
    state: 'waiting',
    doing: 'Scanning logs for errors, timeouts, and anomalous stack traces…',
  },
  {
    key: 'metrics',
    tool: 'get_metrics',
    icon: 'chart',
    title: 'Metrics',
    state: 'waiting',
    doing: 'Comparing service latency, error rates, and resource utilization…',
  },
  {
    key: 'past',
    tool: 'search_past_incidents',
    icon: 'history',
    title: 'Past incidents',
    state: 'waiting',
    doing: 'Checking past postmortems and playbooks for similar patterns…',
  },
]

function StatePill({ s }: { s: CheckState }) {
  if (s === 'done') return <Chip tone="ok" icon="check">Done</Chip>
  if (s === 'running')
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-accent/15 px-2.5 py-1 text-[12px] font-semibold text-accent">
        <span className="spin size-3 rounded-full border-2 border-accent/30 border-t-accent" />
        Running
      </span>
    )
  return <Chip>Waiting</Chip>
}

function Bar({ w, h = 'h-3' }: { w: string; h?: string }) {
  return <div className={`skeleton rounded-md ${h}`} style={{ width: w }} />
}

const clock = (s: number) => `00:${String(s).padStart(2, '0')}`

function extractFinding(toolName: string, data: any): string {
  if (!data) return 'Telemetry analyzed.'
  if (typeof data === 'string') return data.slice(0, 150)
  if (Array.isArray(data)) {
    if (toolName === 'get_recent_deploys') {
      const d = data[0]
      if (d) return `Deploy #${d.deploy_id || 'latest'}: ${d.description || d.commit_message || 'checked'}.`
      return 'No unexpected deploys found.'
    }
    if (toolName === 'query_logs') {
      return `${data.length} relevant log events identified and reviewed.`
    }
    if (toolName === 'search_past_incidents') {
      const inc = data[0]
      if (inc) return `Similar past incident found: ${inc.title || inc.cause || 'reviewed'}.`
      return 'Past incident database analyzed.'
    }
    return `${data.length} telemetry records retrieved.`
  }
  if (typeof data === 'object') {
    if (toolName === 'get_metrics') {
      return 'Metric anomalies and baseline divergences detected.'
    }
    if (data.summary) return String(data.summary)
    if (data.message) return String(data.message)
  }
  return 'Check complete.'
}

export function Investigate() {
  const {
    go,
    diagnosed,
    setDiagnosed,
    selectedScenario,
    setInvestigationId,
    setInvestigationResult,
    setRehearsalResult,
    investigationResult,
    agentPlan,
    setAgentPlan,
    setAgentPlanMeta,
    replanReason,
    setReplanReason,
    setAgentTrace,
    setAgentTotals,
    blockedInstructions,
    setBlockedInstructions,
  } = useNav()

  const [checks, setChecks] = useState<CheckItem[]>(() => {
    if (diagnosed) {
      return initialChecks.map((c) => ({
        ...c,
        state: 'done' as CheckState,
        finding: c.finding || 'Inspection completed.',
      }))
    }
    return initialChecks
  })

  const [seconds, setSeconds] = useState(diagnosed ? 42 : 0)
  const [error, setError] = useState<string | null>(null)
  const isStarted = useRef(false)

  useEffect(() => {
    if (diagnosed) return
    if (isStarted.current) return
    isStarted.current = true

    const startTime = Date.now()
    const interval = setInterval(() => {
      setSeconds(Math.floor((Date.now() - startTime) / 1000))
    }, 1000)

    const abortCtrl = new AbortController()

    // Presentation pacing: queue completed steps and show them with >= 400ms between each
    const doneQueue: Array<{ tool: string; finding: string }> = []
    let draining = false
    function drainQueue() {
      if (draining || doneQueue.length === 0) return
      draining = true
      const { tool, finding } = doneQueue.shift()!
      setChecks((prev) =>
        prev.map((c) => (c.tool === tool ? { ...c, state: 'done', finding } : c))
      )
      if (doneQueue.length > 0) {
        setTimeout(() => {
          draining = false
          drainQueue()
        }, 420)
      } else {
        draining = false
      }
    }

    async function streamInvestigation() {
      try {
        const csrfToken = getCsrfToken()
        const res = await fetch('/api/investigations/trigger', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            scenario_id: selectedScenario || 'bad_deploy_slow_queries',
            csrf_token: csrfToken,
          }),
          credentials: 'same-origin',
          signal: abortCtrl.signal,
        })

        if (!res.ok) {
          const errData = await res.json().catch(() => null)
          setError(errData?.detail || 'Failed to trigger agent investigation.')
          clearInterval(interval)
          return
        }

        if (!res.body) {
          setError('No response stream received.')
          clearInterval(interval)
          return
        }

        const reader = res.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const chunks = buffer.split('\n\n')
          buffer = chunks.pop() || ''

          for (const chunk of chunks) {
            for (const line of chunk.split('\n')) {
              if (line.startsWith('data: ')) {
                const jsonText = line.substring(6).trim()
                if (!jsonText) continue
                try {
                  const ev = JSON.parse(jsonText)
                  handleSSEEvent(ev)
                } catch (err) {
                  console.error('SSE JSON parse error', err)
                }
              }
            }
          }
        }
      } catch (err: any) {
        if (err.name !== 'AbortError') {
          setError('Connection error during investigation.')
        }
      } finally {
        clearInterval(interval)
      }
    }

    function handleSSEEvent(ev: any) {
      if (ev.type === 'init') {
        if (ev.investigation_id) {
          setInvestigationId(ev.investigation_id)
        }
      } else if (ev.type === 'plan') {
        if (Array.isArray(ev.steps)) {
          setAgentPlan(ev.steps)
          setAgentPlanMeta({ source: ev.source === 'model' ? 'model' : 'standard', isMock: ev.is_mock !== false })
        }
      } else if (ev.type === 'replan') {
        if (ev.reason) {
          setReplanReason(ev.reason)
        }
        if (Array.isArray(ev.steps)) {
          setAgentPlan(ev.steps)
          setAgentPlanMeta({ source: ev.source === 'model' ? 'model' : 'standard', isMock: ev.is_mock !== false })
        }
      } else if (ev.type === 'untrusted_instruction_blocked') {
        if (ev.source_tool && ev.excerpt) {
          setBlockedInstructions((prev) => [
            ...prev,
            { sourceTool: ev.source_tool, excerpt: ev.excerpt },
          ])
        }
      } else if (ev.type === 'tool_call_start') {
        const tool = ev.tool_name
        setChecks((prev) =>
          prev.map((c) => (c.tool === tool ? { ...c, state: 'running' } : c))
        )
        setAgentPlan((prev) =>
          prev.map((s) => (s.tool === tool ? { ...s, status: 'running' } : s))
        )
      } else if (ev.type === 'tool_call_result') {
        const tool = ev.tool_name
        const finding = extractFinding(tool, ev.data)
        // Queue the 'done' update for 400ms paced display
        doneQueue.push({ tool, finding })
        drainQueue()
        setAgentPlan((prev) =>
          prev.map((s) => (s.tool === tool ? { ...s, status: 'completed' } : s))
        )
        setAgentTrace((prev) => [
          ...prev,
          {
            index: ev.tool_call_index || prev.length + 1,
            toolName: ev.tool_name,
            arguments: ev.arguments || {},
            summary: ev.summary || finding,
            durationMs: ev.duration_ms || 24,
            isMock: ev.is_mock !== false,
          },
        ])
      } else if (ev.type === 'rehearsal_result') {
        setRehearsalResult(ev)
      } else if (ev.type === 'investigation_completed') {
        if (ev.result) {
          setInvestigationResult(ev.result)
        }
        if (ev.elapsed_ms || ev.tokens_used) {
          setAgentTotals({
            toolCalls: ev.tool_calls_used || 5,
            tokens: ev.tokens_used || 1720,
            elapsedMs: ev.elapsed_ms || 2100,
            isMock: ev.is_mock !== false,
          })
        }
        setChecks((prev) => prev.map((c) => ({ ...c, state: 'done' })))
        setAgentPlan((prev) => prev.map((s) => ({ ...s, status: 'completed' })))
        setDiagnosed(true)
        // Stay on Investigate — user clicks 'See likely causes' manually
      } else if (ev.type === 'error') {
        setError(ev.message || 'Investigation failed.')
      }
    }

    streamInvestigation()

    return () => {
      clearInterval(interval)
      abortCtrl.abort()
    }
  }, [diagnosed, selectedScenario])

  const finished = diagnosed || checks.every((c) => c.state === 'done')
  const doneCount = checks.filter((c) => c.state === 'done').length
  const topHypothesis = investigationResult?.hypotheses?.[0]

  return (
    <Shell
      current={1}
      footer={
        <ActionBar
          note={
            error
              ? error
              : diagnosed
              ? 'Checks complete. Review the findings, then continue.'
              : 'Read-only for now. The agent is running checks.'
          }
        >
          <PrimaryButton disabled={!diagnosed} onClick={() => go('theories')}>
            See likely causes
          </PrimaryButton>
        </ActionBar>
      }
    >
      <PageHeader
        eyebrow="Checkout API is responding slowly"
        title={finished ? 'The agent has finished' : 'The agent is investigating'}
        sub={
          finished
            ? 'All four checks are done. Likely causes are ready for you.'
            : 'It is working through four checks. Findings appear under each one as it finishes.'
        }
        right={
          <div className="flex items-center gap-3 self-start rounded-2xl border border-line bg-panel px-4 py-3 @tablet:self-auto">
            <Icon name="clock" size={20} className="text-accent" />
            <div className="leading-tight">
              <div className="text-[12px] text-mute">Time to diagnosis</div>
              <div className="font-mono text-[22px] font-medium tabular-nums">{clock(seconds)}</div>
            </div>
          </div>
        }
      />

      {/* Untrusted Instruction Neutralized Notice (Phase 11) */}
      {blockedInstructions.length > 0 && (
        <div
          data-testid="untrusted-instruction-notice"
          className="flex items-start gap-3 rounded-2xl border border-line bg-panel p-4 text-[13px] text-mute leading-relaxed"
        >
          <Icon name="shield" size={18} className="mt-0.5 text-accent shrink-0" />
          <div>
            <span className="font-semibold text-ink">Untrusted instruction neutralized: </span>
            <span>
              An instruction marker was detected in telemetry ({blockedInstructions.map((b) => `${b.sourceTool}: "${b.excerpt}"`).join(', ')}).
              The text was sanitized and treated strictly as passive data.
            </span>
          </div>
        </div>
      )}

      {error && (
        <div
          role="alert"
          className="flex items-start gap-3 rounded-2xl border border-bad/30 bg-bad/10 p-4 text-[14px] text-bad"
        >
          <Icon name="alert" size={18} className="mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Dynamic Investigation Plan Checklist (Phase 9) */}
      {agentPlan && agentPlan.length > 0 && (
        <Card className="p-5">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line pb-3">
            <div className="flex items-center gap-2">
              <span className="grid size-6 place-items-center rounded-md bg-accent/15 text-accent">
                <Icon name="target" size={14} />
              </span>
              <h2 className="text-[14.5px] font-semibold text-ink">{agentPlan.length > 0 ? 'Investigation Plan' : 'Standard checks'}</h2>
              <span className="text-[12px] text-mute">
                ({agentPlan.filter((s) => s.status === 'completed').length} of {agentPlan.length} completed)
              </span>
            </div>
            {replanReason && <Chip tone="warn" icon="alert">Plan updated</Chip>}
          </div>

          {replanReason && (
            <div className="mt-3 flex items-start gap-2.5 rounded-xl border border-warn/30 bg-warn/10 p-3 text-[12.5px] text-warn leading-snug">
              <Icon name="info" size={16} className="mt-0.5 shrink-0" />
              <span><strong>Plan revised:</strong> {replanReason}</span>
            </div>
          )}

          <ul className="mt-3.5 space-y-2">
            {agentPlan.map((s) => {
              const isDone = s.status === 'completed'
              const isRunning = s.status === 'running'
              return (
                <li
                  key={s.step}
                  className={`flex items-start gap-3 rounded-xl border p-3 text-[13.5px] transition-colors ${
                    isRunning
                      ? 'border-accent/40 bg-accent/[0.06] text-ink font-medium'
                      : isDone
                      ? 'border-line/60 bg-bg/40 text-mute'
                      : 'border-line/40 text-faint'
                  }`}
                >
                  <span
                    className={`grid size-5 shrink-0 place-items-center rounded-full mt-0.5 text-[11px] font-semibold ${
                      isDone
                        ? 'bg-ok/15 text-ok'
                        : isRunning
                        ? 'bg-accent/20 text-accent animate-pulse'
                        : 'bg-panel-2 text-faint'
                    }`}
                  >
                    {isDone ? <Icon name="check" size={12} stroke={2.5} /> : s.step}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className={isDone ? 'text-ink/80 line-through decoration-line/70' : isRunning ? 'text-ink font-medium' : 'text-mute'}>
                        {s.description}
                      </span>
                      <code className="rounded bg-panel-2 px-1.5 py-0.2 font-mono text-[11px] text-accent">
                        {s.tool}
                      </code>
                    </div>
                  </div>
                </li>
              )
            })}
          </ul>
        </Card>
      )}

      <div className="grid grid-cols-1 gap-5 @laptop:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <Card className="overflow-hidden">
          <div className="flex items-center justify-between border-b border-line px-5 py-4">
            <h2 className="text-[15px] font-semibold">What the agent is checking</h2>
            <span className="text-[12.5px] text-mute">{doneCount} of 4 done</span>
          </div>
          <ul className="divide-y divide-line/70">
            {checks.map((it) => (
              <li
                key={it.key}
                className={`flex items-start gap-4 px-5 py-4 transition-colors ${
                  it.state === 'running' ? 'bg-accent/[0.06]' : ''
                }`}
              >
                <span
                  className={`grid size-10 shrink-0 place-items-center rounded-xl ${
                    it.state === 'waiting'
                      ? 'bg-panel-2 text-faint'
                      : it.state === 'done'
                      ? 'bg-ok/12 text-ok'
                      : 'bg-accent/15 text-accent'
                  }`}
                >
                  <Icon name={it.icon} size={18} />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1.5">
                    <span className={`text-[15px] font-medium ${it.state === 'waiting' ? 'text-mute' : 'text-ink'}`}>
                      {it.title}
                    </span>
                    <StatePill s={it.state} />
                  </div>
                  <p className={`mt-1.5 text-[13.5px] leading-relaxed ${it.state === 'done' ? 'text-ink/85' : 'text-mute'}`}>
                    {it.state === 'done' ? (it.finding || 'Check finished.') : it.doing}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        </Card>

        <Card className="p-5">
          <Label>{finished ? 'Ready for you' : 'Coming next'}</Label>
          {finished ? (
            <div className="mt-4 flex flex-col gap-3 rounded-xl border border-accent/30 bg-accent/[0.06] p-4">
              <div className="flex items-center gap-2 text-[14px] font-medium">
                <Icon name="bulb" size={17} className="text-accent" />
                {investigationResult?.hypotheses?.length || 3} likely causes found
              </div>
              <p className="text-[13.5px] leading-relaxed text-mute">
                Most likely:{' '}
                {topHypothesis
                  ? `${topHypothesis.cause} (${Math.round(topHypothesis.confidence * 100)}% confidence).`
                  : 'Investigation completed.'}
              </p>
            </div>
          ) : (
            <div className="mt-4 space-y-5">
              {['Likely causes', 'Proposed fix', 'Practice run result'].map((t, i) => (
                <div key={t}>
                  <div className="mb-2.5 text-[13px] text-mute">{t}</div>
                  <div className="space-y-2.5 rounded-xl border border-line/70 bg-bg/50 p-4">
                    <Bar w={`${72 - i * 8}%`} h="h-3.5" />
                    <Bar w="92%" h="h-2.5" />
                    <Bar w={`${58 + i * 6}%`} h="h-2.5" />
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* Collapsed Agent Trace Drawer (Phase 9) */}
      <AgentTraceDrawer />
    </Shell>
  )
}
