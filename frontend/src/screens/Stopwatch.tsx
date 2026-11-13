/**
 * Phase 10 — Compare with Manual screen (Stopwatch)
 *
 * Shows:
 *  - Raw log viewer for the current scenario with text filter
 *  - Manual stopwatch: Start → Root cause identified
 *  - Result strip comparing manual time vs agent time-to-diagnosis
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { Shell } from '../components/Frame'
import { Icon } from '../components/Icon'
import { Card, GhostButton, Label, PageHeader, PrimaryButton } from '../components/ui'
import { useNav } from '../nav'

type LogRow = { timestamp: string; level: string; message: string; service?: string }

function fmt(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  const s = Math.floor(ms / 1000)
  const m = Math.floor(s / 60)
  if (m === 0) return `${s}s`
  return `${m}m ${s % 60}s`
}

function fmtClock(ms: number): string {
  const totalSec = Math.floor(ms / 1000)
  const m = Math.floor(totalSec / 60)
  const s = totalSec % 60
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

export function Stopwatch() {
  const { go, selectedScenario, agentTotals } = useNav()

  // ── Log viewer state ──────────────────────────────────────────────────────
  const [logs, setLogs] = useState<LogRow[]>([])
  const [filter, setFilter] = useState('')
  const [logsError, setLogsError] = useState<string | null>(null)
  const [logsLoading, setLogsLoading] = useState(true)

  useEffect(() => {
    setLogsLoading(true)
    setLogsError(null)
    fetch(`/api/scenarios/${selectedScenario}/raw_logs`, { credentials: 'same-origin' })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then((data) => setLogs(data.logs ?? []))
      .catch((e) => setLogsError(e.message))
      .finally(() => setLogsLoading(false))
  }, [selectedScenario])

  const filteredLogs = filter.trim()
    ? logs.filter(
        (l) =>
          l.message.toLowerCase().includes(filter.toLowerCase()) ||
          (l.service ?? '').toLowerCase().includes(filter.toLowerCase()) ||
          l.level.toLowerCase().includes(filter.toLowerCase()),
      )
    : logs

  // ── Manual stopwatch state ────────────────────────────────────────────────
  const [stopwatchState, setStopwatchState] = useState<'idle' | 'running' | 'done'>('idle')
  const [manualElapsedMs, setManualElapsedMs] = useState<number>(0)
  const startTsRef = useRef<number | null>(null)
  const rafRef = useRef<number | null>(null)

  const tick = useCallback(() => {
    if (startTsRef.current === null) return
    setManualElapsedMs(Date.now() - startTsRef.current)
    rafRef.current = requestAnimationFrame(tick)
  }, [])

  const handleStart = () => {
    startTsRef.current = Date.now()
    setManualElapsedMs(0)
    setStopwatchState('running')
    rafRef.current = requestAnimationFrame(tick)
  }

  const handleIdentified = () => {
    if (rafRef.current !== null) cancelAnimationFrame(rafRef.current)
    if (startTsRef.current !== null) setManualElapsedMs(Date.now() - startTsRef.current)
    setStopwatchState('done')
  }

  const handleReset = () => {
    if (rafRef.current !== null) cancelAnimationFrame(rafRef.current)
    startTsRef.current = null
    setManualElapsedMs(0)
    setStopwatchState('idle')
  }

  useEffect(() => () => { if (rafRef.current !== null) cancelAnimationFrame(rafRef.current) }, [])

  // ── Result comparison ─────────────────────────────────────────────────────
  const agentMs = agentTotals?.elapsedMs ?? null
  const fasterBy =
    stopwatchState === 'done' && agentMs !== null ? manualElapsedMs - agentMs : null

  return (
    <Shell
      current={-1 /* not a main-flow step */}
      footer={
        <div className="flex items-center justify-between gap-4 px-5 py-3">
          <GhostButton onClick={() => go('theories')}>
            <Icon name="arrow-left" size={16} className="mr-1.5" />
            Back to theories
          </GhostButton>
        </div>
      }
    >
      <PageHeader
        eyebrow="Practice mode"
        title="Compare with manual"
        sub="Browse the raw logs and time yourself finding the root cause. See how you stack up against the agent."
      />

      {/* ── Side-by-side layout ──────────────────────────────────────────── */}
      <div className="grid grid-cols-1 gap-5 @laptop:grid-cols-[1fr_320px]">

        {/* Raw log viewer */}
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-3">
            <label htmlFor="log-filter" className="sr-only">Filter logs</label>
            <div className="relative flex-1">
              <Icon name="search" size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-mute" />
              <input
                id="log-filter"
                data-testid="log-filter"
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                placeholder="Filter logs…"
                className="h-10 w-full rounded-xl border border-line bg-bg pl-9 pr-4 text-[13.5px] outline-none placeholder:text-faint focus:border-accent/60"
              />
            </div>
            {filter && (
              <GhostButton onClick={() => setFilter('')}>Clear</GhostButton>
            )}
          </div>

          <Card className="p-0 overflow-hidden">
            {logsLoading && (
              <div className="flex items-center justify-center gap-2 py-12 text-mute text-[14px]">
                <Icon name="loader" size={18} className="animate-spin" />
                Loading logs…
              </div>
            )}
            {logsError && (
              <div className="flex items-center gap-2 py-8 px-5 text-bad text-[14px]">
                <Icon name="alert" size={16} />
                Failed to load logs: {logsError}
              </div>
            )}
            {!logsLoading && !logsError && (
              <div
                data-testid="log-viewer"
                className="max-h-[460px] overflow-y-auto font-mono text-[12px] leading-relaxed"
                role="log"
                aria-label="Raw scenario logs"
              >
                {filteredLogs.length === 0 ? (
                  <p className="py-10 text-center text-mute">No log lines match "{filter}"</p>
                ) : (
                  filteredLogs.map((row, i) => (
                    <div
                      key={i}
                      className={`flex gap-3 border-b border-line/50 px-4 py-1 last:border-0 ${
                        row.level === 'ERROR' ? 'bg-bad/5 text-bad' : 'text-ink/80'
                      }`}
                    >
                      <span className="shrink-0 text-faint">{row.timestamp}</span>
                      <span
                        className={`w-14 shrink-0 font-semibold ${
                          row.level === 'ERROR'
                            ? 'text-bad'
                            : row.level === 'WARN'
                            ? 'text-warn'
                            : 'text-mute'
                        }`}
                      >
                        {row.level}
                      </span>
                      <span className="break-words">{row.message}</span>
                    </div>
                  ))
                )}
              </div>
            )}
          </Card>

          {!logsLoading && !logsError && (
            <p className="text-right text-[12px] text-faint">
              {filteredLogs.length} of {logs.length} lines
            </p>
          )}
        </div>

        {/* Stopwatch panel */}
        <div className="flex flex-col gap-4">
          <Card className="p-5">
            <Label>Your stopwatch</Label>
            <div
              data-testid="stopwatch-display"
              className="my-5 text-center font-mono text-[48px] font-bold tabular-nums leading-none tracking-tight text-ink"
            >
              {fmtClock(manualElapsedMs)}
            </div>

            {stopwatchState === 'idle' && (
              <PrimaryButton
                onClick={handleStart}
                icon="play"
                data-testid="start-stopwatch"
                className="w-full justify-center"
              >
                Start
              </PrimaryButton>
            )}

            {stopwatchState === 'running' && (
              <PrimaryButton
                onClick={handleIdentified}
                icon="check"
                data-testid="identify-button"
                className="w-full justify-center"
              >
                Root cause identified
              </PrimaryButton>
            )}

            {stopwatchState === 'done' && (
              <>
                <div className="mb-3 flex items-center gap-2 rounded-xl border border-ok/30 bg-ok/10 px-4 py-2.5 text-ok">
                  <Icon name="check" size={16} />
                  <span className="text-[13.5px] font-medium">
                    Manual time: {fmt(manualElapsedMs)}
                  </span>
                </div>
                <GhostButton
                  onClick={handleReset}
                  data-testid="reset-stopwatch"
                  className="w-full justify-center"
                >
                  Reset
                </GhostButton>
              </>
            )}

            <p className="mt-4 text-center text-[12px] text-faint">
              {stopwatchState === 'idle' && 'Press Start, browse the logs, then press "Root cause identified" when you know the answer.'}
              {stopwatchState === 'running' && 'Clock is running…'}
              {stopwatchState === 'done' && 'Timer stopped.'}
            </p>
          </Card>

          {/* Agent time card */}
          <Card className="p-5">
            <Label>Agent time-to-diagnosis</Label>
            <div className="mt-3 text-center font-mono text-[36px] font-bold tabular-nums leading-none text-accent">
              {agentMs !== null ? fmt(agentMs) : '—'}
            </div>
            {agentTotals?.isMock && (
              <p className="mt-1 text-center text-[11.5px] text-faint">(simulated)</p>
            )}
            {agentMs === null && (
              <p className="mt-2 text-center text-[12px] text-faint">
                Run an investigation first to see the agent's time.
              </p>
            )}
          </Card>

          {/* Result strip */}
          {stopwatchState === 'done' && agentMs !== null && (
            <Card
              data-testid="result-strip"
              className={`p-5 ${fasterBy !== null && fasterBy > 0 ? 'border-ok/30 bg-ok/5' : 'border-accent/30 bg-accent/5'}`}
            >
              <Label>Result</Label>
              <div className="mt-3 space-y-2 text-[14px]">
                <div className="flex justify-between">
                  <span className="text-mute">Your time</span>
                  <span className="font-semibold tabular-nums">{fmt(manualElapsedMs)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-mute">Agent time</span>
                  <span className="font-semibold tabular-nums text-accent">{fmt(agentMs)}</span>
                </div>
                <div className="mt-3 border-t border-line pt-3 flex justify-between font-semibold">
                  <span>
                    {fasterBy !== null && fasterBy > 0 ? '🤖 Agent was faster' : '🏆 You were faster'}
                  </span>
                  <span className={fasterBy !== null && fasterBy > 0 ? 'text-accent' : 'text-ok'}>
                    {fasterBy !== null ? `by ${fmt(Math.abs(fasterBy))}` : ''}
                  </span>
                </div>
              </div>
            </Card>
          )}

          {stopwatchState === 'done' && agentMs === null && (
            <Card className="p-5">
              <p className="text-[13.5px] text-mute">
                No agent time recorded for this session. Run an investigation on the Investigate screen to compare.
              </p>
            </Card>
          )}
        </div>
      </div>
    </Shell>
  )
}
