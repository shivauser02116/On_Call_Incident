import { Icon } from './Icon'

export function Card({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return <div className={`rounded-2xl border border-line bg-panel ${className}`}>{children}</div>
}

export function PageHeader({ eyebrow, title, sub, right }: { eyebrow?: React.ReactNode; title: string; sub?: string; right?: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-4 @tablet:flex-row @tablet:items-end @tablet:justify-between">
      <div className="min-w-0">
        {eyebrow && <div className="mb-2 text-[12px] font-medium uppercase tracking-[0.12em] text-faint">{eyebrow}</div>}
        <h1 className="text-[24px] font-semibold leading-tight tracking-tight @laptop:text-[30px]">{title}</h1>
        {sub && <p className="mt-1.5 max-w-[60ch] text-[14.5px] leading-relaxed text-mute">{sub}</p>}
      </div>
      {right}
    </div>
  )
}

export function Label({ children }: { children: React.ReactNode }) {
  return <div className="text-[12px] font-medium uppercase tracking-[0.1em] text-faint">{children}</div>
}

export function Chip({ tone = 'mute', icon, children }: { tone?: 'bad' | 'accent' | 'ok' | 'mute'; icon?: string; children: React.ReactNode }) {
  const t = { bad: 'bg-bad/15 text-bad', accent: 'bg-accent/15 text-accent', ok: 'bg-ok/12 text-ok', mute: 'bg-panel-2 text-mute' }[tone]
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[12px] font-semibold ${t}`}>
      {icon && <Icon name={icon} size={13} stroke={2} />}
      {children}
    </span>
  )
}

export function PrimaryButton({ children, disabled, icon = 'arrow', className = '', onClick }: { children: React.ReactNode; disabled?: boolean; icon?: string | null; className?: string; onClick?: () => void }) {
  return (
    <button
      disabled={disabled}
      onClick={onClick}
      className={`flex h-12 min-w-11 items-center justify-center gap-2 rounded-xl px-6 text-[15px] font-semibold transition-colors ${
        disabled ? 'cursor-not-allowed bg-panel-2 text-faint' : 'bg-accent text-bg shadow-[0_10px_28px_-10px_rgba(139,147,255,0.85)] hover:bg-accent-strong'
      } ${className}`}
    >
      {children}
      {icon && <Icon name={icon} size={17} stroke={2.2} />}
    </button>
  )
}

export function GhostButton({ children, className = '', onClick }: { children: React.ReactNode; className?: string; onClick?: () => void }) {
  return <button onClick={onClick} className={`flex h-12 min-w-11 items-center justify-center rounded-xl border border-line px-6 text-[15px] font-medium text-ink hover:bg-panel-2 ${className}`}>{children}</button>
}

export function DemoTag() {
  return (
    <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full border border-line px-2.5 py-0.5 text-[11px] text-faint">
      <span className="size-1 rounded-full bg-faint" /> Demo data
    </span>
  )
}

const levels = [
  { key: 'safe', label: 'Safe', on: 'bg-ok/15 text-ok ring-ok/40' },
  { key: 'reversible', label: 'Reversible', on: 'bg-accent/15 text-accent ring-accent/40' },
  { key: 'risky', label: 'Risky', on: 'bg-bad/15 text-bad ring-bad/40' },
] as const

export type Risk = (typeof levels)[number]['key']

export function RiskScale({ level }: { level: Risk }) {
  return (
    <div role="img" aria-label={`Risk level: ${level}`} className="grid grid-cols-3 gap-1.5 rounded-xl border border-line bg-bg p-1.5">
      {levels.map((l, i) => {
        const active = l.key === level
        return (
          <div key={l.key} className={`flex min-h-11 items-center justify-center gap-1.5 rounded-lg px-1 text-[13px] font-medium ring-1 ${active ? l.on : 'text-faint ring-transparent'}`}>
            <span className={`grid size-4 place-items-center rounded-full text-[10px] font-semibold`}>
              {active ? <Icon name="check" size={13} stroke={2.6} /> : i + 1}
            </span>
            {l.label}
          </div>
        )
      })}
    </div>
  )
}
