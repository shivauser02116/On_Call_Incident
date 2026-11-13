import { useState } from 'react'
import { ActionBar, Shell } from '../components/Frame'
import { Icon } from '../components/Icon'
import { getCsrfToken, useNav } from '../nav'
import { Card, Chip, GhostButton, Label, PageHeader, PrimaryButton, RiskScale, type Risk } from '../components/ui'

function Row({ icon, label, children }: { icon: string; label: string; children: React.ReactNode }) {
  return (
    <Card className="p-5">
      <div className="flex items-center gap-2.5 text-accent">
        <Icon name={icon} size={17} />
        <Label>{label}</Label>
      </div>
      <div className="mt-3">{children}</div>
    </Card>
  )
}

/** Shown when top confidence < 50% or no confident fix can be proposed. */
function EscalationView({
  hypotheses,
  investigationId,
}: {
  hypotheses: Array<{ rank: number; cause: string; confidence: number }>
  investigationId: number | null
}) {
  const [submitting, setSubmitting] = useState(false)
  const [escalated, setEscalated] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  const handleEscalate = async () => {
    if (!investigationId) {
      setEscalated(true)
      return
    }
    setSubmitting(true)
    setErrorMsg(null)
    try {
      const csrfToken = getCsrfToken()
      const res = await fetch(`/api/investigations/${investigationId}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          investigation_id: investigationId,
          action: 'escalate',
          csrf_token: csrfToken,
        }),
        credentials: 'same-origin',
      })
      if (res.ok) {
        setEscalated(true)
      } else {
        const data = await res.json().catch(() => null)
        setErrorMsg(data?.detail || 'Failed to escalate.')
      }
    } catch {
      setErrorMsg('Network error while escalating.')
    } finally {
      setSubmitting(false)
    }
  }

  const conflictingReasons = hypotheses
    .slice(0, 3)
    .map((h) => `${Math.round(h.confidence * 100)}% — ${h.cause}`)

  const suggestedChecks = [
    'Run tcpdump / traceroute on affected edge nodes and inspect packet loss.',
    'Check DNS resolver logs for intermittent NXDOMAIN or timeout patterns.',
    'Pull CPU and memory graphs for all worker nodes over the incident window.',
  ]

  if (escalated) {
    return (
      <Shell current={4}>
        <PageHeader
          eyebrow="Investigation complete"
          title="Escalated to a human"
          sub="An audit entry has been recorded. A Tier-3 engineer will take over."
        />
        <Card className="p-6">
          <div className="flex items-center gap-3 text-ok">
            <Icon name="check" size={22} />
            <span className="text-[16px] font-semibold">Escalation logged</span>
          </div>
          <p className="mt-3 text-[14px] text-mute">
            This investigation has been marked for human review. No automated fix was applied.
          </p>
        </Card>
      </Shell>
    )
  }

  return (
    <Shell
      current={4}
      footer={
        <ActionBar
          note={
            <span className="text-mute text-[13.5px]">
              No automated fix is safe to apply. Escalate for human review.
            </span>
          }
        >
          <PrimaryButton
            icon="alert"
            onClick={handleEscalate}
            disabled={submitting}
            data-testid="escalate-button"
          >
            {submitting ? 'Escalating…' : 'Escalate to a human'}
          </PrimaryButton>
        </ActionBar>
      }
    >
      <PageHeader
        eyebrow="Checkout API is responding slowly"
        title="No safe fix found"
        sub="The agent found conflicting evidence across hypotheses. Confidence is too low to apply an automated fix safely."
      />

      {errorMsg && (
        <div
          role="alert"
          className="flex items-start gap-3 rounded-2xl border border-bad/30 bg-bad/10 p-4 text-[14px] text-bad"
        >
          <Icon name="alert" size={18} className="mt-0.5 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      <Card className="border-warn/30 bg-warn/5 p-5">
        <div className="flex items-center gap-2.5 text-warn">
          <Icon name="alert" size={17} />
          <Label>Conflicting evidence — hypotheses could not be ranked with confidence</Label>
        </div>
        <ul className="mt-3 space-y-1.5">
          {conflictingReasons.map((r) => (
            <li key={r} className="flex items-start gap-2 text-[13.5px] text-mute">
              <span className="mt-0.5 shrink-0 text-warn">•</span>
              <span>{r}</span>
            </li>
          ))}
        </ul>
      </Card>

      <Card className="p-5">
        <div className="flex items-center gap-2.5 text-accent">
          <Icon name="list" size={17} />
          <Label>Suggested read-only checks for the on-call engineer</Label>
        </div>
        <ol className="mt-3 space-y-2">
          {suggestedChecks.map((c, i) => (
            <li key={i} className="flex items-start gap-2.5 text-[13.5px]">
              <span className="mt-0.5 shrink-0 font-semibold text-accent">{i + 1}.</span>
              <span className="text-mute">{c}</span>
            </li>
          ))}
        </ol>
      </Card>
    </Shell>
  )
}

export function Decision() {
  const { go, variant, investigationResult, rehearsalResult, investigationId } = useNav()

  const proposedFix = investigationResult?.proposed_fix
  const topHypothesis = investigationResult?.hypotheses?.[0]
  const allHypotheses = investigationResult?.hypotheses ?? []

  // Phase 10: detect escalation path
  const topConfidence = topHypothesis
    ? (topHypothesis.confidence > 1 ? topHypothesis.confidence / 100 : topHypothesis.confidence)
    : null
  const needsEscalation = topConfidence !== null && topConfidence < 0.5

  if (needsEscalation) {
    return (
      <EscalationView
        hypotheses={allHypotheses}
        investigationId={investigationId}
      />
    )
  }

  const numericRisk = proposedFix?.risk_level ?? (variant === 'risky' ? 2 : 1)
  const riskKey: Risk = numericRisk === 0 ? 'safe' : numericRisk === 2 ? 'risky' : 'reversible'
  const risky = riskKey === 'risky'

  const fixId = proposedFix?.fix_id || 'fix_add_index'
  const expectedPhrase = `CONFIRM ${fixId}`

  const [typed, setTyped] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  const blocked = risky && typed.trim() !== expectedPhrase
  const fix = proposedFix?.action || (risky ? 'Restart the orders database' : 'Re-create index on orders(customer_id)')

  // Section D: colon-split fix action
  const fixColonIdx = fix.indexOf(':')
  const fixHeadline = fixColonIdx > 0 ? fix.slice(0, fixColonIdx).trim() : null
  const fixDetail = fixColonIdx > 0 ? fix.slice(fixColonIdx + 1).trim() : null
  const impact = proposedFix?.blast_radius || rehearsalResult?.blast_radius || (risky ? 'All checkouts, for about 2 minutes' : 'Checkout API only')
  const causeTitle = topHypothesis?.cause || 'Missing database index after a recent change'
  const causeConf = topHypothesis
    ? Math.round(topHypothesis.confidence > 1 ? topHypothesis.confidence : topHypothesis.confidence * 100)
    : 82

  const stats = [
    ['Response time', '2,340 → 190 ms'],
    ['Errors', '6.8% → 0.4%'],
    ['Database connections', '96 → 41'],
  ]

  const handleDecision = async (action: 'approve' | 'reject') => {
    if (!investigationId) {
      // If demo navigation with no real investigation, proceed directly
      if (action === 'approve') go('success')
      else go('theories')
      return
    }

    setSubmitting(true)
    setErrorMsg(null)
    try {
      const csrfToken = getCsrfToken()
      const res = await fetch(`/api/investigations/${investigationId}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          investigation_id: investigationId,
          action,
          confirmation_text: risky ? typed.trim() : undefined,
          csrf_token: csrfToken,
        }),
        credentials: 'same-origin',
      })

      if (res.ok) {
        if (action === 'approve') {
          go('success')
        } else {
          go('theories')
        }
      } else {
        const data = await res.json().catch(() => null)
        setErrorMsg(data?.detail || `Failed to ${action} fix.`)
      }
    } catch {
      setErrorMsg('Network error while processing decision.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Shell
      current={4}
      footer={
        <ActionBar
          note={
            <>
              <span className="font-medium text-ink">Nothing runs until you approve.</span>
              {blocked && <span className="hidden @tablet:inline"> Type {expectedPhrase} to enable Approve.</span>}
            </>
          }
        >
          <GhostButton disabled={submitting} onClick={() => handleDecision('reject')}>
            Reject
          </GhostButton>
          <PrimaryButton
            disabled={blocked || submitting}
            icon="check"
            onClick={() => handleDecision('approve')}
          >
            {submitting ? 'Applying…' : 'Approve fix'}
          </PrimaryButton>
        </ActionBar>
      }
    >
      <PageHeader
        eyebrow="Checkout API is responding slowly"
        title="Review and decide"
        sub="Here is everything in one place. Approve to run the fix, or reject to stop."
      />

      {errorMsg && (
        <div
          role="alert"
          className="flex items-start gap-3 rounded-2xl border border-bad/30 bg-bad/10 p-4 text-[14px] text-bad"
        >
          <Icon name="alert" size={18} className="mt-0.5 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 @tablet:grid-cols-2 @laptop:gap-5">
        <Row icon="bulb" label="Cause">
          <div className="flex items-start justify-between gap-3">
            <p className="text-[16px] font-medium leading-snug">{causeTitle}</p>
            <span className="text-[22px] font-semibold tabular-nums leading-none">{causeConf}%</span>
          </div>
          <div className="mt-3">
            <Chip tone="accent">Most likely</Chip>
          </div>
        </Row>

        <Row icon="wrench" label="Fix">
          {fixHeadline ? (
            <>
              <p className="break-words text-[16px] font-medium leading-snug">{fixHeadline}</p>
              <div className="mt-2">
                <div className="mb-1 text-[11.5px] font-medium uppercase tracking-wider text-mute">Exact change</div>
                <pre className="overflow-x-auto rounded-lg border border-line bg-bg px-3 py-2 font-mono text-[12.5px] text-ink/90 whitespace-pre-wrap break-words">
                  {fixDetail}
                </pre>
              </div>
            </>
          ) : (
            <p className="break-words text-[16px] font-medium leading-snug">{fix}</p>
          )}
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
          <div className="mt-3">
            <Chip tone="ok" icon="check">Practice run passed</Chip>
          </div>
        </Row>

        <Row icon="shield" label="Risk">
          <RiskScale level={riskKey} assignedReason={impact} />
        </Row>
      </div>

      {risky && (
        <Card className="border-bad/30 p-5">
          <label htmlFor="confirm" className="flex items-center gap-2.5 text-[15px] font-semibold text-bad">
            <Icon name="lock" size={17} /> Type {expectedPhrase} to continue
          </label>
          <p className="mt-1.5 text-[13.5px] text-mute">
            Because this fix is risky (Level 2), Approve stays disabled until you type the exact phrase below.
          </p>
          <input
            id="confirm"
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            placeholder={expectedPhrase}
            autoComplete="off"
            className={`mt-4 h-12 w-full rounded-xl border bg-bg px-4 font-mono text-[15px] tracking-wider outline-none placeholder:text-faint @tablet:max-w-sm ${
              typed && blocked
                ? 'border-bad/50'
                : typed && !blocked
                ? 'border-ok/60'
                : 'border-line focus:border-accent/60'
            }`}
          />
        </Card>
      )}
    </Shell>
  )
}
