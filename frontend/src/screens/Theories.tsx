import { useState } from 'react'
import { ActionBar, Shell } from '../components/Frame'
import { Icon } from '../components/Icon'
import { useNav } from '../nav'
import { Card, Chip, PageHeader, PrimaryButton } from '../components/ui'

interface TheoryItem {
  title: string
  confidence: number
  forItems: string[]
  againstItems: string[]
  log?: string[]
}

function List({ kind, items }: { kind: 'for' | 'against'; items: string[] }) {
  const f = kind === 'for'
  return (
    <div>
      <div className={`mb-3 text-[12px] font-semibold uppercase tracking-[0.1em] ${f ? 'text-ok' : 'text-warn'}`}>
        {f ? 'Evidence for' : 'Evidence against'}
      </div>
      <ul className="space-y-2.5">
        {items.length === 0 ? (
          <li className="text-[13.5px] italic text-faint">None noted</li>
        ) : (
          items.map((e, idx) => (
            <li key={idx} className="flex gap-2.5 text-[14px] leading-snug text-ink/90">
              <Icon
                name={f ? 'plus' : 'minus'}
                size={15}
                stroke={2.2}
                className={`mt-0.5 shrink-0 ${f ? 'text-ok' : 'text-warn'}`}
              />
              <span>{e}</span>
            </li>
          ))
        )}
      </ul>
    </div>
  )
}

function Theory({
  t,
  rank,
  open,
  onToggle,
}: {
  t: TheoryItem
  rank: number
  open: boolean
  onToggle: () => void
}) {
  const top = rank === 1
  const total = t.forItems.length + t.againstItems.length || 1
  const forPct = Math.round((t.forItems.length / total) * 100)

  return (
    <article
      className={`overflow-hidden rounded-2xl border bg-panel ${
        top ? 'border-accent/45 shadow-[0_18px_50px_-28px_rgba(139,147,255,0.6)]' : 'border-line'
      }`}
    >
      <button onClick={onToggle} aria-expanded={open} className="block w-full p-4 text-left @tablet:p-5">
        <div className="flex items-start gap-3 @tablet:gap-4">
          <span
            className={`grid size-9 shrink-0 place-items-center rounded-full text-[14px] font-semibold ${
              top ? 'bg-accent text-bg' : 'bg-panel-2 text-mute'
            }`}
          >
            {rank}
          </span>
          <div className="min-w-0 flex-1">
            {top && (
              <div className="mb-1.5">
                <Chip tone="accent">Most likely</Chip>
              </div>
            )}
            <h2 className="text-[16px] font-medium leading-snug">{t.title}</h2>
          </div>
          <div className="shrink-0 text-right leading-none">
            <div className={`text-[26px] font-semibold tabular-nums ${top ? 'text-ink' : 'text-mute'}`}>
              {t.confidence}%
            </div>
            <div className="mt-1 text-[11px] text-faint">confidence</div>
          </div>
        </div>

        <div className="mt-4 @tablet:pl-[3.25rem]">
          <div className="flex items-center justify-between text-[12px] text-faint">
            <span>Evidence balance</span>
            <span className="flex items-center gap-1.5 text-mute">
              {open ? 'Hide details' : 'See details'}
              <Icon name="chevron" size={16} className={`transition-transform ${open ? 'rotate-180' : ''}`} />
            </span>
          </div>
          <div className="mt-2 flex h-2 gap-0.5 overflow-hidden rounded-full">
            <div className="rounded-l-full bg-ok" style={{ width: `${forPct}%` }} />
            <div className="flex-1 rounded-r-full bg-warn" />
          </div>
          <div className="mt-1.5 flex justify-between text-[12px]">
            <span className="text-ok">{t.forItems.length} for</span>
            <span className="text-warn">{t.againstItems.length} against</span>
          </div>
        </div>
      </button>

      {open && (
        <div className="border-t border-line px-4 py-5 @tablet:px-5 @tablet:pl-[4.75rem]">
          <div className="grid grid-cols-1 gap-6 @tablet:grid-cols-2">
            <List kind="for" items={t.forItems} />
            <List kind="against" items={t.againstItems} />
          </div>
          {t.log && t.log.length > 0 && (
            <div className="mt-6 overflow-hidden rounded-xl border border-line bg-bg">
              <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
                <Chip icon="logs">Log data</Chip>
                <span className="text-[12px] text-faint">Evidence citation</span>
              </div>
              <pre className="overflow-x-auto px-4 py-3 font-mono text-[12.5px] leading-relaxed text-mute">
                {t.log.join('\n')}
              </pre>
            </div>
          )}
        </div>
      )}
    </article>
  )
}

export function Theories({ initialOpen = [0] }: { initialOpen?: number[] }) {
  const [openSet, setOpen] = useState<number[]>(initialOpen)
  const { go, investigationResult } = useNav()

  const toggle = (i: number) =>
    setOpen((o) => (o.includes(i) ? o.filter((x) => x !== i) : [...o, i]))

  const rawHypotheses = investigationResult?.hypotheses || []

  const displayedTheories: TheoryItem[] = rawHypotheses.length > 0
    ? rawHypotheses.map((h) => {
        const conf = typeof h.confidence === 'number'
          ? Math.round(h.confidence > 1 ? h.confidence : h.confidence * 100)
          : 50
        const logSnippets: string[] = []
        h.evidence_for?.forEach((e) => {
          if (e.source_row) logSnippets.push(e.source_row)
        })
        return {
          title: h.cause,
          confidence: conf,
          forItems: (h.evidence_for || []).map((e) => e.description),
          againstItems: (h.evidence_against || []).map((e) => e.description),
          log: logSnippets.length > 0 ? logSnippets : undefined,
        }
      })
    : [
        {
          title: 'Missing database index after a recent change',
          confidence: 82,
          forItems: [
            'Release #4821 (02:14 AM) changed how orders are looked up',
            'Database load rose from 35% to 92% right after it',
            'Log lines confirm full table scan on orders table',
          ],
          againstItems: ['Other services on the same database look normal'],
        },
      ]

  return (
    <Shell
      current={2}
      footer={
        <ActionBar note="Next, review the fix the agent proposes for the most likely cause.">
          <PrimaryButton onClick={() => go('fix')}>Review fix</PrimaryButton>
        </ActionBar>
      }
    >
      <PageHeader
        eyebrow="Checkout API is responding slowly"
        title={`${displayedTheories.length} likely causes`}
        sub="Ranked by how well the evidence fits. Open any cause to see why."
      />

      {!investigationResult && (
        <Card className="border-warn/30 bg-warn/10 p-4 text-[13.5px] text-warn">
          Showing preview hypotheses. Run an investigation from Alert to view real-time agent output.
        </Card>
      )}

      <div className="flex flex-col gap-3 @laptop:gap-4">
        {displayedTheories.map((t, i) => (
          <Theory
            key={t.title + i}
            t={t}
            rank={i + 1}
            open={openSet.includes(i)}
            onToggle={() => toggle(i)}
          />
        ))}
      </div>
    </Shell>
  )
}
