import { useState } from 'react'
import { ActionBar, Shell } from '../components/Frame'
import { Icon } from '../components/Icon'
import { useNav } from '../nav'
import { Chip, PageHeader, PrimaryButton } from '../components/ui'

const theories = [
  {
    title: 'Missing database index after a recent change',
    confidence: 82,
    forItems: ['Release #4821 (02:14 AM) changed how orders are looked up', 'Database load rose from 35% to 92% right after it', '1,204 log lines say a query took over 2 seconds', 'The slow step is the same one that changed', 'A similar incident in March had the same cause'],
    againstItems: ['Other services on the same database look normal'],
    log: [
      '02:16:41 WARN  orders.lookup  query took 2,142 ms (customer_id = 48213)',
      '02:16:41 WARN  orders.lookup  full table scan on orders, 1.8M rows read',
      '02:16:42 ERROR checkout.pay   timed out waiting for orders (3,000 ms)',
    ],
  },
  {
    title: 'Connection pool saturation',
    confidence: 11,
    forItems: ['Open database connections are high (96 of 100)', 'Some requests waited for a free connection'],
    againstItems: ['Connections only filled up after queries got slow', 'No new traffic that would explain the rise', 'Servers are using normal memory and CPU'],
  },
  {
    title: 'Upstream payment provider slowdown',
    confidence: 7,
    forItems: ['9 payment requests timed out in the last hour'],
    againstItems: ['Provider status page shows all systems normal', 'Slowness starts before the payment step', 'Other customers of the provider report no issues'],
  },
]

function List({ kind, items }: { kind: 'for' | 'against'; items: string[] }) {
  const f = kind === 'for'
  return (
    <div>
      <div className={`mb-3 text-[12px] font-semibold uppercase tracking-[0.1em] ${f ? 'text-ok' : 'text-warn'}`}>{f ? 'Evidence for' : 'Evidence against'}</div>
      <ul className="space-y-2.5">
        {items.map((e) => (
          <li key={e} className="flex gap-2.5 text-[14px] leading-snug text-ink/90">
            <Icon name={f ? 'plus' : 'minus'} size={15} stroke={2.2} className={`mt-0.5 shrink-0 ${f ? 'text-ok' : 'text-warn'}`} />
            {e}
          </li>
        ))}
      </ul>
    </div>
  )
}

function Theory({ t, rank, open, onToggle }: { t: (typeof theories)[number]; rank: number; open: boolean; onToggle: () => void }) {
  const top = rank === 1
  const total = t.forItems.length + t.againstItems.length
  const forPct = (t.forItems.length / total) * 100
  return (
    <article className={`overflow-hidden rounded-2xl border bg-panel ${top ? 'border-accent/45 shadow-[0_18px_50px_-28px_rgba(139,147,255,0.6)]' : 'border-line'}`}>
      <button onClick={onToggle} aria-expanded={open} className="block w-full p-4 text-left @tablet:p-5">
        <div className="flex items-start gap-3 @tablet:gap-4">
          <span className={`grid size-9 shrink-0 place-items-center rounded-full text-[14px] font-semibold ${top ? 'bg-accent text-bg' : 'bg-panel-2 text-mute'}`}>{rank}</span>
          <div className="min-w-0 flex-1">
            {top && <div className="mb-1.5"><Chip tone="accent">Most likely</Chip></div>}
            <h2 className="text-[16px] font-medium leading-snug">{t.title}</h2>
          </div>
          <div className="shrink-0 text-right leading-none">
            <div className={`text-[26px] font-semibold tabular-nums ${top ? 'text-ink' : 'text-mute'}`}>{t.confidence}%</div>
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
          {t.log && (
            <div className="mt-6 overflow-hidden rounded-xl border border-line bg-bg">
              <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
                <Chip icon="logs">Log data</Chip>
                <span className="text-[12px] text-faint">02:16 AM</span>
              </div>
              <pre className="overflow-x-auto px-4 py-3 font-mono text-[12.5px] leading-relaxed text-mute">{t.log.join('\n')}</pre>
            </div>
          )}
        </div>
      )}
    </article>
  )
}

export function Theories({ initialOpen = [0] }: { initialOpen?: number[] }) {
  const [openSet, setOpen] = useState<number[]>(initialOpen)
  const { go, rejected, setRejected } = useNav()
  const toggle = (i: number) => setOpen((o) => (o.includes(i) ? o.filter((x) => x !== i) : [...o, i]))
  return (
    <Shell
      current={2}
      footer={
        <ActionBar note="Next, review the fix the agent proposes for the most likely cause.">
          <PrimaryButton onClick={() => go('fix')}>Review fix</PrimaryButton>
        </ActionBar>
      }
    >
      <PageHeader eyebrow="Checkout API is responding slowly" title="Three likely causes" sub="Ranked by how well the evidence fits. Open any cause to see why." />
      {rejected && (
        <div role="status" className="flex items-start gap-3 rounded-2xl border border-bad/35 bg-bad/10 px-5 py-4">
          <Icon name="shield" size={18} className="mt-0.5 shrink-0 text-bad" />
          <div className="min-w-0">
            <div className="text-[14px] font-semibold text-bad">Fix rejected</div>
            <div className="mt-0.5 text-[13px] text-mute">You rejected the proposed fix. Review the theories below and select a different approach, or escalate.</div>
          </div>
          <button type="button" onClick={() => setRejected(false)} aria-label="Dismiss" className="ml-auto shrink-0 rounded-lg p-1 text-faint transition-colors hover:text-ink">
            <Icon name="x" size={16} />
          </button>
        </div>
      )}
      <div className="flex flex-col gap-3 @laptop:gap-4">
        {theories.map((t, i) => (
          <Theory key={t.title} t={t} rank={i + 1} open={openSet.includes(i)} onToggle={() => toggle(i)} />
        ))}
      </div>
    </Shell>
  )
}
