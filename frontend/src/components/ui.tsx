import { useState } from 'react'
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

export function PrimaryButton({ children, disabled, icon = 'arrow', className = '', onClick, ...rest }: React.ButtonHTMLAttributes<HTMLButtonElement> & { children: React.ReactNode; icon?: string | null }) {
  return (
    <button
      disabled={disabled}
      onClick={onClick}
      className={`flex h-12 min-w-11 items-center justify-center gap-2 rounded-xl px-6 text-[15px] font-semibold transition-colors ${
        disabled ? 'cursor-not-allowed bg-panel-2 text-faint' : 'bg-accent text-bg shadow-[0_10px_28px_-10px_rgba(139,147,255,0.85)] hover:bg-accent-strong'
      } ${className}`}
      {...rest}
    >
      {children}
      {icon && <Icon name={icon} size={17} stroke={2.2} />}
    </button>
  )
}

export function GhostButton({ children, className = '', onClick, disabled, ...rest }: React.ButtonHTMLAttributes<HTMLButtonElement> & { children: React.ReactNode }) {
  return <button onClick={onClick} disabled={disabled} className={`flex h-12 min-w-11 items-center justify-center rounded-xl border border-line px-6 text-[15px] font-medium text-ink hover:bg-panel-2 disabled:opacity-50 disabled:cursor-not-allowed ${className}`} {...rest}>{children}</button>
}

export function DemoTag() {
  return (
    <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full border border-line px-2.5 py-0.5 text-[11px] text-faint">
      <span className="size-1 rounded-full bg-faint" /> Demo data
    </span>
  )
}

const levels = [
  {
    key: 'safe',
    label: 'Safe',
    on: 'bg-ok/15 text-ok ring-ok/40',
    explanation: 'Read-only or no effect on live systems.',
  },
  {
    key: 'reversible',
    label: 'Reversible',
    on: 'bg-accent/15 text-accent ring-accent/40',
    explanation: 'Changes something, but it can be undone.',
  },
  {
    key: 'risky',
    label: 'Risky',
    on: 'bg-bad/15 text-bad ring-bad/40',
    explanation: 'Hard or impossible to undo. Needs a typed confirmation.',
  },
] as const

export type Risk = (typeof levels)[number]['key']

export function RiskScale({ level, assignedReason }: { level: Risk; assignedReason?: string }) {
  const [expanded, setExpanded] = useState<Risk | null>(null)

  const toggle = (key: Risk) => {
    setExpanded((prev) => (prev === key ? null : key))
  }

  const expandedLevel = levels.find((l) => l.key === expanded)

  return (
    <div>
      {/* Three keyboard-accessible buttons — tapping shows explanation, never changes risk level */}
      <div className="grid grid-cols-3 gap-1.5 rounded-xl border border-line bg-bg p-1.5">
        {levels.map((l, i) => {
          const active = l.key === level
          const isExpanded = expanded === l.key
          return (
            <button
              key={l.key}
              type="button"
              id={`risk-btn-${l.key}`}
              aria-expanded={isExpanded}
              aria-controls={`risk-panel-${l.key}`}
              onClick={() => toggle(l.key)}
              className={`flex min-h-[44px] items-center justify-center gap-1.5 rounded-lg px-1 text-[13px] font-medium ring-1 transition-colors ${
                active ? l.on : 'text-faint ring-transparent hover:text-mute hover:ring-line/50'
              } focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent`}
            >
              <span className="grid size-4 place-items-center rounded-full text-[10px] font-semibold">
                {active ? <Icon name="check" size={13} stroke={2.6} /> : i + 1}
              </span>
              <span className="flex flex-col items-start leading-tight">
                <span>{l.label}</span>
                {active && (
                  <span className="text-[10px] font-normal opacity-80">Assigned</span>
                )}
              </span>
            </button>
          )
        })}
      </div>

      {/* Explanation panel (read-only context) */}
      {expandedLevel && (
        <div
          id={`risk-panel-${expandedLevel.key}`}
          role="region"
          aria-labelledby={`risk-btn-${expandedLevel.key}`}
          className="mt-2 rounded-xl border border-line bg-panel p-3.5 text-[13px] leading-relaxed text-mute"
        >
          <span className="font-medium text-ink">{expandedLevel.label}: </span>
          {expandedLevel.explanation}
          {expandedLevel.key === level && assignedReason && (
            <p className="mt-2 text-[12px] text-faint italic">{assignedReason}</p>
          )}
        </div>
      )}

      {/* Read-only caption */}
      <p className="mt-2 text-[11.5px] text-faint">
        Set by the agent. Enforced when you approve.
      </p>
    </div>
  )
}

