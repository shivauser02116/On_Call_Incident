import { PracticeChart } from '../components/Charts'
import { ActionBar, Shell } from '../components/Frame'
import { Icon } from '../components/Icon'
import { useNav } from '../nav'
import { Card, Chip, Label, PageHeader, PrimaryButton, RiskScale } from '../components/ui'

const results = [
  { label: 'Response time', before: '2,340', after: '190', unit: 'ms', change: '92% faster' },
  { label: 'Errors', before: '6.8%', after: '0.4%', unit: '', change: '94% fewer' },
  { label: 'Database connections', before: '96', after: '41', unit: '', change: '57% fewer' },
]

export function Fix() {
  const { go } = useNav()
  return (
    <Shell
      current={3}
      footer={
        <ActionBar note="Next, review everything and make your decision.">
          <PrimaryButton onClick={() => go('decision')}>Continue to decision</PrimaryButton>
        </ActionBar>
      }
    >
      <PageHeader eyebrow="Checkout API is responding slowly" title="Proposed fix and practice run" sub="The agent tried this fix in a safe copy first. Real customers were not affected." />

      <Card className="p-5 @laptop:p-6">
        <div className="grid grid-cols-1 gap-6 @laptop:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)] @laptop:gap-10">
          <div>
            <div className="flex items-center gap-2 text-accent"><Icon name="wrench" size={17} /><Label>Proposed fix</Label></div>
            <h2 className="mt-3 text-[20px] font-semibold leading-snug @laptop:text-[22px]">
              Re-create index on <span className="break-words font-mono text-[0.9em] text-accent">orders(customer_id)</span>
            </h2>
            <p className="mt-3 text-[14.5px] leading-relaxed text-mute">
              A recent change removed the shortcut the database uses to find a customer’s orders, so it now reads the whole table every time. Putting the shortcut back makes lookups fast again.
            </p>
          </div>
          <div className="space-y-4">
            <div>
              <div className="mb-2.5 flex items-center justify-between"><Label>Risk</Label><span className="text-[12.5px] text-mute">Can be undone</span></div>
              <RiskScale level="reversible" />
            </div>
            <div className="flex items-center gap-3 rounded-xl border border-line bg-bg px-4 py-3">
              <Icon name="target" size={18} className="shrink-0 text-accent" />
              <div className="leading-tight">
                <div className="text-[12px] text-mute">Impact</div>
                <div className="mt-0.5 text-[14.5px] font-medium">Checkout API only</div>
              </div>
            </div>
          </div>
        </div>
      </Card>

      <Card className="p-5 @laptop:p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-accent"><Icon name="flask" size={17} /><Label>Practice run result</Label></div>
          <Chip tone="ok" icon="check">Practice run passed</Chip>
        </div>

        <div className="mt-5 grid grid-cols-1 gap-3 @laptop:grid-cols-3 @laptop:gap-4">
          {results.map((r) => (
            <div key={r.label} className="rounded-xl border border-line bg-bg p-4">
              <div className="text-[13px] text-mute">{r.label}</div>
              <div className="mt-3 flex flex-wrap items-baseline gap-x-2.5 gap-y-1 tabular-nums">
                <span className="text-[22px] text-mute line-through decoration-faint/60">{r.before}</span>
                <Icon name="arrow" size={16} className="self-center text-faint" />
                <span className="text-[32px] font-semibold leading-none">{r.after}</span>
                {r.unit && <span className="text-[14px] text-mute">{r.unit}</span>}
              </div>
              <div className="mt-3"><Chip tone="ok">{r.change}</Chip></div>
            </div>
          ))}
        </div>

        <div className="mt-6">
          <div className="mb-3 text-[13px] text-mute">Response time during the practice run</div>
          <PracticeChart />
        </div>
      </Card>
    </Shell>
  )
}
