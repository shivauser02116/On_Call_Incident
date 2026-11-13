import { ActionBar, Shell } from '../components/Frame'
import { Icon } from '../components/Icon'
import { useNav } from '../nav'
import { Card, PrimaryButton } from '../components/ui'

const now = [
  ['Response time', '190 ms', 'was 2,340 ms'],
  ['Errors', '0.4%', 'was 6.8%'],
  ['Database connections', '41', 'was 96'],
]

export function Success() {
  const { go, setDiagnosed, setRejected } = useNav()
  return (
    <Shell
      current={5}
      footer={
        <ActionBar note="Everything the agent did is saved in the incident log.">
          <PrimaryButton icon={null} onClick={() => { setDiagnosed(false); setRejected(false); go('alert') }}>Back to start</PrimaryButton>
        </ActionBar>
      }
    >
      <div className="mx-auto flex w-full max-w-2xl flex-col items-center py-4 text-center @laptop:py-10">
        <div className="relative grid size-20 place-items-center rounded-full bg-ok/12 text-ok ring-1 ring-ok/30">
          <span className="absolute inset-0 rounded-full bg-ok/10 blur-xl" />
          <Icon name="check" size={36} stroke={2} className="relative" />
        </div>
        <h1 className="mt-7 text-[28px] font-semibold leading-tight tracking-tight @laptop:text-[36px]">Fix approved and applied</h1>
        <p className="mt-3 max-w-[48ch] text-[15.5px] leading-relaxed text-mute">
          <span className="break-words font-mono text-[0.92em] text-ink">orders(customer_id)</span> now has its index again. Checkout API is back to normal speed and customers can pay without waiting.
        </p>

        <Card className="mt-9 w-full p-2">
          <ul className="divide-y divide-line/70">
            {now.map(([label, value, was]) => (
              <li key={label} className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 px-4 py-3.5">
                <span className="text-[14px] text-mute">{label}</span>
                <span className="flex items-baseline gap-3 tabular-nums">
                  <span className="text-[12.5px] text-faint">{was}</span>
                  <span className="text-[18px] font-semibold text-ok">{value}</span>
                </span>
              </li>
            ))}
          </ul>
        </Card>
        <p className="mt-5 flex items-center gap-2 text-[13px] text-faint">
          <Icon name="undo" size={14} /> This change can be undone at any time.
        </p>
      </div>
    </Shell>
  )
}
