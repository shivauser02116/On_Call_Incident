import { Spark } from '../components/Charts'
import { ActionBar, Shell } from '../components/Frame'
import { Icon } from '../components/Icon'
import { useNav } from '../nav'
import { Card, Chip, Label, PrimaryButton } from '../components/ui'

function Number({ label, value, unit, normal, factor, points }: { label: string; value: string; unit?: string; normal: string; factor: string; points: number[] }) {
  return (
    <Card className="p-5 @laptop:p-6">
      <div className="flex items-center justify-between gap-3">
        <Label>{label}</Label>
        <Chip tone="bad">{factor}</Chip>
      </div>
      <div className="mt-3 flex items-baseline gap-2">
        <span className="text-[40px] font-semibold leading-none tracking-tight tabular-nums @laptop:text-[48px]">{value}</span>
        {unit && <span className="text-[18px] text-mute">{unit}</span>}
      </div>
      <div className="mt-2 text-[13.5px] text-mute">{normal}</div>
      <div className="mt-4"><Spark points={points} /></div>
    </Card>
  )
}

const checks = [
  { icon: 'code', label: 'Recent changes' },
  { icon: 'logs', label: 'Logs' },
  { icon: 'chart', label: 'Metrics' },
  { icon: 'history', label: 'Past incidents' },
]

export function Alert() {
  const { go, setDiagnosed } = useNav()
  return (
    <Shell
      current={0}
      footer={
        <ActionBar note="The agent only reads data. It will not change anything.">
          <PrimaryButton icon="play" onClick={() => { setDiagnosed(false); go('investigate') }}>Start investigation</PrimaryButton>
        </ActionBar>
      }
    >
      <Card className="relative overflow-hidden border-bad/25 bg-gradient-to-br from-bad/10 via-panel to-panel p-5 @laptop:p-8">
        <div className="flex flex-wrap items-center gap-2">
          <Chip tone="bad">SEV 2</Chip>
          <Chip icon="database">Checkout API</Chip>
          <span className="flex items-center gap-1.5 pl-1 text-[13px] text-mute">
            <Icon name="clock" size={15} /> Triggered 02:31 AM
          </span>
        </div>
        <div className="mt-5 flex items-start gap-4">
          <span className="hidden size-12 shrink-0 place-items-center rounded-xl bg-bad/15 text-bad @tablet:grid">
            <Icon name="alert" size={24} />
          </span>
          <div>
            <h1 className="text-[26px] font-semibold leading-tight tracking-tight @laptop:text-[34px]">Checkout API is responding slowly</h1>
            <p className="mt-2 max-w-[56ch] text-[15px] leading-relaxed text-mute">Some customers are waiting a long time to pay, and a few are seeing errors. It started about 4 minutes ago.</p>
          </div>
        </div>
      </Card>

      <div className="grid grid-cols-1 gap-4 @tablet:grid-cols-2 @laptop:gap-5">
        <Number label="Response time" value="2,340" unit="ms" normal="Normal is about 200 ms" factor="12× slower" points={[3, 3, 4, 3, 5, 18, 26, 28, 27, 29]} />
        <Number label="Errors" value="6.8%" normal="Normal is under 0.5%" factor="14× higher" points={[2, 2, 3, 2, 3, 9, 20, 24, 27, 26]} />
      </div>

      <div>
        <Label>Next, the agent will look at</Label>
        <div className="mt-3 grid grid-cols-2 gap-3 @laptop:grid-cols-4">
          {checks.map((c) => (
            <div key={c.label} className="flex min-h-11 items-center gap-3 rounded-xl border border-line bg-panel px-4 py-3">
              <Icon name={c.icon} size={18} className="shrink-0 text-accent" />
              <span className="text-[14px] text-ink/90">{c.label}</span>
            </div>
          ))}
        </div>
      </div>
    </Shell>
  )
}
