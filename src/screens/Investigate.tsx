import { useEffect, useState } from 'react'
import { ActionBar, Shell } from '../components/Frame'
import { Icon } from '../components/Icon'
import { useNav } from '../nav'
import { Card, Chip, Label, PageHeader, PrimaryButton } from '../components/ui'

type State = 'done' | 'running' | 'waiting'

const items = [
  { icon: 'code', title: 'Recent changes', finding: 'Release #4821 at 02:14 AM changed how orders are looked up.' },
  { icon: 'logs', title: 'Logs', finding: '1,204 log lines say a database query took over 2 seconds.' },
  { icon: 'chart', title: 'Metrics', finding: 'Database load jumped from 35% to 92% at 02:15 AM.', doing: 'Comparing database, servers and network with normal…' },
  { icon: 'history', title: 'Past incidents', finding: 'A similar slowdown in March was fixed by restoring an index.', doing: 'Looks for similar problems and how they were solved.' },
]

// phase 0: metrics running · 1: past incidents running · 2: everything done
function stateOf(i: number, phase: number): State {
  if (i < 2) return 'done'
  const step = i - 2
  return phase > step ? 'done' : phase === step ? 'running' : 'waiting'
}

function StatePill({ s }: { s: State }) {
  if (s === 'done') return <Chip tone="ok" icon="check">Done</Chip>
  if (s === 'running') return <span className="inline-flex items-center gap-1.5 rounded-full bg-accent/15 px-2.5 py-1 text-[12px] font-semibold text-accent"><span className="spin size-3 rounded-full border-2 border-accent/30 border-t-accent" />Running</span>
  return <Chip>Waiting</Chip>
}

function Bar({ w, h = 'h-3' }: { w: string; h?: string }) {
  return <div className={`skeleton rounded-md ${h}`} style={{ width: w }} />
}

const clock = (s: number) => `00:${String(s).padStart(2, '0')}`

export function Investigate() {
  const { go, diagnosed, setDiagnosed } = useNav()
  const [phase, setPhase] = useState(diagnosed ? 2 : 0)
  const [seconds, setSeconds] = useState(diagnosed ? 51 : 48)

  // Simulates the agent finishing: checks complete one by one, then move on after 3 seconds.
  useEffect(() => {
    if (diagnosed) return
    const timers = [
      setTimeout(() => setPhase(1), 1100),
      setTimeout(() => setPhase(2), 2300),
      setTimeout(() => { setDiagnosed(true); go('theories') }, 3000),
    ]
    const tick = setInterval(() => setSeconds((s) => Math.min(s + 1, 51)), 1000)
    return () => { timers.forEach(clearTimeout); clearInterval(tick) }
  }, [])

  const finished = phase >= 2
  const doneCount = items.filter((_, i) => stateOf(i, phase) === 'done').length

  return (
    <Shell
      current={1}
      footer={
        <ActionBar note={diagnosed ? 'The checks are finished. Review the likely causes.' : 'Read-only for now. You will move on automatically when the checks finish.'}>
          <PrimaryButton disabled={!diagnosed} onClick={() => go('theories')}>See likely causes</PrimaryButton>
        </ActionBar>
      }
    >
      <PageHeader
        eyebrow="Checkout API is responding slowly"
        title={finished ? 'The agent has finished' : 'The agent is investigating'}
        sub={finished ? 'All four checks are done. Likely causes are ready for you.' : 'It is working through four checks. Findings appear under each one as it finishes.'}
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

      <div className="grid grid-cols-1 gap-5 @laptop:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <Card className="overflow-hidden">
          <div className="flex items-center justify-between border-b border-line px-5 py-4">
            <h2 className="text-[15px] font-semibold">What the agent is checking</h2>
            <span className="text-[12.5px] text-mute">{doneCount} of 4 done</span>
          </div>
          <ul className="divide-y divide-line/70">
            {items.map((it, i) => {
              const state = stateOf(i, phase)
              return (
                <li key={it.title} className={`flex items-start gap-4 px-5 py-4 transition-colors ${state === 'running' ? 'bg-accent/[0.06]' : ''}`}>
                  <span className={`grid size-10 shrink-0 place-items-center rounded-xl ${state === 'waiting' ? 'bg-panel-2 text-faint' : state === 'done' ? 'bg-ok/12 text-ok' : 'bg-accent/15 text-accent'}`}>
                    <Icon name={it.icon} size={18} />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1.5">
                      <span className={`text-[15px] font-medium ${state === 'waiting' ? 'text-mute' : 'text-ink'}`}>{it.title}</span>
                      <StatePill s={state} />
                    </div>
                    <p className={`mt-1.5 text-[13.5px] leading-relaxed ${state === 'done' ? 'text-ink/85' : 'text-mute'}`}>{state === 'done' ? it.finding : it.doing}</p>
                  </div>
                </li>
              )
            })}
          </ul>
        </Card>

        <Card className="p-5">
          <Label>{finished ? 'Ready for you' : 'Coming next'}</Label>
          {finished ? (
            <div className="mt-4 flex flex-col gap-3 rounded-xl border border-accent/30 bg-accent/[0.06] p-4">
              <div className="flex items-center gap-2 text-[14px] font-medium"><Icon name="bulb" size={17} className="text-accent" /> 3 likely causes found</div>
              <p className="text-[13.5px] leading-relaxed text-mute">Most likely: a missing database index after a recent change (82% confidence).</p>
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
    </Shell>
  )
}
