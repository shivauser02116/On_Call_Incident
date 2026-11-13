import { backOf, stepRoutes, useNav, type Route } from '../nav'
import { DemoTag } from './ui'
import { Icon, Logo } from './Icon'
import { UserMenu } from './UserMenu'

export const steps = [
  { label: 'Alert', hint: 'What broke', icon: 'alert' },
  { label: 'Investigate', hint: 'Agent checks', icon: 'search' },
  { label: 'Theories', hint: 'Likely causes', icon: 'bulb' },
  { label: 'Fix & practice run', hint: 'Tested safely', icon: 'wrench' },
  { label: 'Your decision', hint: 'Approve or reject', icon: 'shield' },
]

function Sidebar({ current }: { current: number }) {
  const { go } = useNav()
  return (
    <aside className="hidden shrink-0 flex-col items-center border-r border-line bg-[#090c12] px-3 py-6 @tablet:flex @laptop:w-[19%] @laptop:min-w-[14rem] @laptop:max-w-[17.5rem] @laptop:items-stretch @laptop:px-5">
      <div className="flex items-center gap-3">
        <Logo />
        <div className="hidden leading-tight @laptop:block">
          <div className="text-[14px] font-semibold">OnCall Rehearsal</div>
          <div className="text-[12px] text-mute">Agent</div>
        </div>
      </div>

      <div className="mt-10 hidden text-[11px] font-medium uppercase tracking-[0.12em] text-faint @laptop:block">Incident flow</div>
      <ol className="mt-10 flex flex-col items-center @laptop:mt-4 @laptop:items-stretch">
        {steps.map((s, i) => {
          const done = i < current
          const active = i === current
          return (
            <li key={s.label} aria-current={active ? 'step' : undefined} className="relative">
              {i < steps.length - 1 && <span className={`absolute left-[15px] top-8 h-[calc(100%-2rem)] w-px ${done ? 'bg-accent/40' : 'bg-line'}`} />}
              <button
                type="button"
                disabled={!done}
                title={s.label}
                aria-label={done ? `Go back to ${s.label}` : s.label}
                onClick={() => go(stepRoutes[i])}
                className={`group relative flex gap-3 text-left ${i === steps.length - 1 ? '' : 'pb-6'} ${done ? 'cursor-pointer' : 'cursor-default'}`}
              >
                <span
                  className={`z-10 grid size-8 shrink-0 place-items-center rounded-full ring-1 transition-colors ${
                    done ? 'bg-accent/15 text-accent ring-accent/30 group-hover:bg-accent/25' : active ? 'bg-accent text-bg ring-accent pulse-ring' : 'bg-panel text-faint ring-line'
                  }`}
                >
                  <Icon name={done ? 'check' : s.icon} size={15} stroke={done ? 2.2 : 1.8} />
                </span>
                <div className="hidden pt-0.5 leading-tight @laptop:block">
                  <div className={`text-[13.5px] font-medium ${active ? 'text-ink' : done ? 'text-ink/80 group-hover:text-ink' : 'text-faint'}`}>{s.label}</div>
                  <div className="mt-0.5 text-[12px] text-faint">{s.hint}</div>
                </div>
              </button>
            </li>
          )
        })}
      </ol>

      <div className="mt-auto flex items-center gap-3 rounded-2xl border border-line bg-panel p-1.5 @laptop:px-3 @laptop:py-3">
        <div className="grid size-8 shrink-0 place-items-center rounded-full bg-panel-2 text-[12px] font-semibold text-accent">MR</div>
        <div className="hidden leading-tight @laptop:block">
          <div className="text-[13px] font-medium">Maya Reyes</div>
          <div className="text-[12px] text-mute">On call tonight</div>
        </div>
      </div>
    </aside>
  )
}

function MobileStepper({ current }: { current: number }) {
  const finished = current >= steps.length
  const profile = current < 0
  const s = finished ? { label: 'All done', icon: 'check' } : profile ? { label: 'Profile', icon: 'user' } : steps[current]
  return (
    <div className="flex shrink-0 items-center gap-3 border-b border-line bg-[#090c12] px-4 py-3 @tablet:hidden">
      <span className={`grid size-10 shrink-0 place-items-center rounded-full ${profile ? 'bg-panel-2 text-mute' : 'bg-accent text-bg'} ${finished || profile ? '' : 'pulse-ring'}`}>
        <Icon name={s.icon} size={17} />
      </span>
      <div className="min-w-0 flex-1 leading-tight">
        <div className="text-[11px] font-medium uppercase tracking-[0.12em] text-faint">{finished ? 'Step 5 of 5' : profile ? 'Your account' : `Step ${current + 1} of ${steps.length}`}</div>
        <div className="truncate text-[16px] font-semibold">{s.label}</div>
      </div>
      <div className="flex items-center gap-1.5" role="img" aria-label={finished ? 'All steps complete' : profile ? 'No step selected' : `Step ${current + 1} of ${steps.length}`}>
        {steps.map((_, i) => (
          <span key={i} className={`h-2 rounded-full ${i < current ? 'w-2 bg-accent/50' : i === current ? 'w-5 bg-accent shadow-[0_0_10px_rgba(139,147,255,0.8)]' : 'w-2 bg-line'}`} />
        ))}
      </div>
      <UserMenu mode="sheet" />
    </div>
  )
}

/** Sticky bar holding the one clear next action. */
export function ActionBar({ note, children }: { note: React.ReactNode; children: React.ReactNode }) {
  return (
    <footer className="screen-in shrink-0 border-t border-line bg-[#0a0d14] px-4 pb-4 pt-3 @tablet:px-8 @laptop:px-10">
      <div className="flex flex-col gap-3 @tablet:flex-row @tablet:items-center @tablet:justify-between">
        <div className="flex items-center justify-between gap-4 @tablet:justify-start">
          <p className="min-w-0 text-[13px] leading-snug text-mute @tablet:text-[13.5px]">{note}</p>
          <DemoTag />
        </div>
        <div className="flex gap-3 [&>*]:flex-1 @tablet:[&>*]:flex-none">{children}</div>
      </div>
    </footer>
  )
}

export function Shell({ current, footer, children }: { current: number; footer: React.ReactNode; children: React.ReactNode }) {
  const { route, go, cameFrom } = useNav()
  const back: Route | undefined = route === 'profile' ? cameFrom : backOf[route]
  return (
    <div className="flex h-full w-full flex-col bg-bg @tablet:flex-row">
      <MobileStepper current={current} />
      <Sidebar current={current} />
      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <header className="relative z-40 hidden min-h-14 shrink-0 items-center justify-between border-b border-line px-8 py-1.5 @tablet:flex @laptop:px-10">
          <div className="flex items-center gap-2 text-[13px] text-mute">
            <span>Incidents</span>
            <span className="text-faint">/</span>
            <span className="text-ink">INC-2048</span>
          </div>
          <div className="flex items-center gap-3 @laptop:gap-5">
            <div className="flex items-center gap-2 text-[12.5px] text-mute">
              <Icon name="clock" size={15} /> Alert received 02:31 AM
            </div>
            <UserMenu mode="bar" />
          </div>
        </header>
        <main className="min-h-0 flex-1 overflow-y-auto px-4 py-5 @tablet:px-8 @tablet:py-6 @laptop:px-10 @laptop:py-8">
          <div className="screen-in mx-auto flex w-full max-w-5xl flex-col gap-5 @laptop:gap-6">
            {back && (
              <button type="button" onClick={() => go(back)} className="-ml-2 inline-flex min-h-11 items-center gap-2 self-start rounded-lg px-2 text-[14px] text-mute transition-colors hover:text-ink">
                <Icon name="arrow" size={16} className="rotate-180" /> Back
              </button>
            )}
            {children}
          </div>
        </main>
        {footer}
      </div>
    </div>
  )
}
