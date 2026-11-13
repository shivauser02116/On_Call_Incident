import { useState } from 'react'
import { ActionBar, Shell } from '../components/Frame'
import { Icon } from '../components/Icon'
import { useNav } from '../nav'
import { Card, Chip, GhostButton, Label, PageHeader, PrimaryButton, RiskScale } from '../components/ui'

function Row({ icon, label, children }: { icon: string; label: string; children: React.ReactNode }) {
  return (
    <Card className="p-5">
      <div className="flex items-center gap-2.5 text-accent"><Icon name={icon} size={17} /><Label>{label}</Label></div>
      <div className="mt-3">{children}</div>
    </Card>
  )
}

const stats = [
  ['Response time', '2,340 → 190 ms'],
  ['Errors', '6.8% → 0.4%'],
  ['Database connections', '96 → 41'],
]

export function Decision() {
  const { go, variant, setRejected } = useNav()
  const risk = variant === 'risky' ? 'risky' : 'reversible'
  const risky = risk === 'risky'
  const [typed, setTyped] = useState('')
  const blocked = risky && typed !== 'CONFIRM'
  const fix = risky ? 'Restart the orders database' : 'Re-create index on orders(customer_id)'
  const impact = risky ? 'All checkouts, for about 2 minutes' : 'Checkout API only'

  return (
    <Shell
      current={4}
      footer={
        <ActionBar
          note={
            <>
              <span className="font-medium text-ink">Nothing runs until you approve.</span>
              {blocked && <span className="hidden @tablet:inline"> Type CONFIRM to enable Approve.</span>}
            </>
          }
        >
          <GhostButton onClick={() => { setRejected(true); go('theories') }}>Reject</GhostButton>
          <PrimaryButton disabled={blocked} icon="check" onClick={() => { setRejected(false); go('success') }}>Approve fix</PrimaryButton>
        </ActionBar>
      }
    >
      <PageHeader eyebrow="Checkout API is responding slowly" title="Review and decide" sub="Here is everything in one place. Approve to run the fix, or reject to stop." />

      <div className="grid grid-cols-1 gap-4 @tablet:grid-cols-2 @laptop:gap-5">
        <Row icon="bulb" label="Cause">
          <div className="flex items-start justify-between gap-3">
            <p className="text-[16px] font-medium leading-snug">Missing database index after a recent change</p>
            <span className="text-[22px] font-semibold tabular-nums leading-none">82%</span>
          </div>
          <div className="mt-3"><Chip tone="accent">Most likely</Chip></div>
        </Row>

        <Row icon="wrench" label="Fix">
          <p className="break-words text-[16px] font-medium leading-snug">{fix}</p>
          <p className="mt-2 text-[13.5px] text-mute">Impact: {impact}</p>
        </Row>

        <Row icon="flask" label="Practice run result">
          <ul className="space-y-2.5">
            {stats.map(([k, v]) => (
              <li key={k} className="flex flex-wrap items-baseline justify-between gap-x-3 text-[14px]">
                <span className="text-mute">{k}</span>
                <span className="font-semibold tabular-nums text-ok">{v}</span>
              </li>
            ))}
          </ul>
          <div className="mt-3"><Chip tone="ok" icon="check">Practice run passed</Chip></div>
        </Row>

        <Row icon="shield" label="Risk">
          <RiskScale level={risk} />
          <p className="mt-3 text-[13.5px] text-mute">{risky ? 'This change is hard to undo. Take a moment before you approve.' : 'You can undo this in one click if anything looks wrong.'}</p>
        </Row>
      </div>

      {risky && (
        <Card className="border-bad/30 p-5">
          <label htmlFor="confirm" className="flex items-center gap-2.5 text-[15px] font-semibold text-bad">
            <Icon name="lock" size={17} /> Type CONFIRM to continue
          </label>
          <p className="mt-1.5 text-[13.5px] text-mute">Because this fix is risky, Approve stays off until you type the word below.</p>
          <input
            id="confirm"
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            placeholder="CONFIRM"
            autoComplete="off"
            className={`mt-4 h-12 w-full rounded-xl border bg-bg px-4 font-mono text-[15px] tracking-wider outline-none placeholder:text-faint @tablet:max-w-sm ${typed && blocked ? 'border-bad/50' : typed ? 'border-ok/60' : 'border-line focus:border-accent/60'}`}
          />
        </Card>
      )}
    </Shell>
  )
}
