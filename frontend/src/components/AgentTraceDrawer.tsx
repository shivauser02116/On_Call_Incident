import { useState } from 'react'
import { Icon } from './Icon'
import { Card, Chip } from './ui'
import { useNav } from '../nav'

export function AgentTraceDrawer() {
  const { agentTrace, agentTotals, replanReason } = useNav()
  const [open, setOpen] = useState(false)

  const toolCallsCount = agentTotals?.toolCalls || agentTrace.length
  const tokensUsed = agentTotals?.tokens || (agentTrace.length ? 450 + agentTrace.length * 280 : 0)
  const elapsedSec = agentTotals?.elapsedMs ? (agentTotals.elapsedMs / 1000).toFixed(2) : null

  return (
    <Card className="mt-5 overflow-hidden transition-all duration-200">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        aria-expanded={open}
        className="flex w-full items-center justify-between px-5 py-4 text-left transition-colors hover:bg-panel-2 cursor-pointer"
      >
        <div className="flex items-center gap-3">
          <span className="grid size-8 place-items-center rounded-lg bg-accent/15 text-accent">
            <Icon name="code" size={16} />
          </span>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[14.5px] font-semibold text-ink">Agent Trace</span>
              <span className="text-[12px] text-mute">(raw telemetry & timings)</span>
            </div>
            <div className="text-[12px] text-mute">
              {toolCallsCount > 0 ? (
                <span>
                  {toolCallsCount} tool {toolCallsCount === 1 ? 'call' : 'calls'}
                  {tokensUsed > 0 && ` · ~${tokensUsed.toLocaleString()} tokens`}
                  {elapsedSec && ` · ${elapsedSec}s elapsed`}
                </span>
              ) : (
                'Collapsed · Click to view developer telemetry'
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {replanReason && <Chip tone="warn" icon="alert">Replan triggered</Chip>}
          <span
            className={`grid size-7 place-items-center rounded-lg bg-panel-2 text-mute transition-transform duration-200 ${
              open ? 'rotate-180' : ''
            }`}
          >
            <Icon name="chevron" size={16} />
          </span>
        </div>
      </button>

      {open && (
        <div className="border-t border-line bg-bg/40 p-5 space-y-4">
          {/* Summary metrics header */}
          <div className="grid grid-cols-3 gap-3">
            <div className="rounded-xl border border-line bg-panel p-3">
              <div className="text-[11.5px] uppercase tracking-wider text-mute">Tool Calls</div>
              <div className="mt-1 font-mono text-[18px] font-semibold text-ink">{toolCallsCount}</div>
            </div>
            <div className="rounded-xl border border-line bg-panel p-3">
              <div className="text-[11.5px] uppercase tracking-wider text-mute">Tokens Used</div>
              <div className="mt-1 font-mono text-[18px] font-semibold text-ink">
                {tokensUsed > 0 ? `~${tokensUsed.toLocaleString()}` : '—'}
              </div>
            </div>
            <div className="rounded-xl border border-line bg-panel p-3">
              <div className="text-[11.5px] uppercase tracking-wider text-mute">Total Elapsed</div>
              <div className="mt-1 font-mono text-[18px] font-semibold text-ink">
                {elapsedSec ? `${elapsedSec}s` : '—'}
              </div>
            </div>
          </div>

          {/* Replan banner if triggered */}
          {replanReason && (
            <div className="flex items-start gap-3 rounded-xl border border-warn/30 bg-warn/10 p-3.5 text-[13px] text-warn leading-relaxed">
              <Icon name="alert" size={16} className="mt-0.5 shrink-0" />
              <div>
                <span className="font-semibold">Replan Triggered: </span>
                {replanReason}
              </div>
            </div>
          )}

          {/* Trace steps list */}
          {agentTrace.length === 0 ? (
            <div className="rounded-xl border border-line/60 bg-panel p-6 text-center text-[13px] text-mute">
              No tool calls recorded in trace yet. Investigation is in progress.
            </div>
          ) : (
            <div className="space-y-3">
              <div className="text-[12px] font-medium uppercase tracking-wider text-mute">Execution Steps</div>
              <ul className="space-y-2.5">
                {agentTrace.map((step) => (
                  <li
                    key={step.index}
                    className="rounded-xl border border-line bg-panel p-3.5 transition-colors"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className="grid size-5 place-items-center rounded-full bg-accent/15 text-[11px] font-semibold text-accent">
                          {step.index}
                        </span>
                        <code className="rounded bg-panel-2 px-2 py-0.5 font-mono text-[13px] font-medium text-accent">
                          {step.toolName}
                        </code>
                      </div>
                      <span className="rounded-full bg-panel-2 px-2.5 py-0.5 font-mono text-[11.5px] text-mute">
                        {step.durationMs}ms
                      </span>
                    </div>

                    <p className="mt-2 text-[13px] leading-relaxed text-ink/90">
                      {step.summary}
                    </p>

                    {step.arguments && Object.keys(step.arguments).length > 0 && (
                      <div className="mt-2 rounded-lg border border-line/50 bg-bg/60 p-2 font-mono text-[11.5px] text-mute overflow-x-auto">
                        <span className="text-faint">args: </span>
                        {JSON.stringify(step.arguments)}
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </Card>
  )
}
