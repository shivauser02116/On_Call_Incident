/**
 * Phase 12 — Incident Memory: Record Outcome Card
 *
 * Allows on-call engineer to record a one-line outcome after Approve or Reject.
 * Stored as plain text in SQLite incident_memory table.
 */
import { useState } from 'react'
import { Icon } from './Icon'
import { Card, GhostButton, PrimaryButton } from './ui'
import { getCsrfToken } from '../nav'

export function RecordOutcomeCard({
  scenarioId,
  cause,
  fix,
  defaultOutcome = 'worked',
  onDone,
}: {
  scenarioId: string
  cause: string
  fix: string
  defaultOutcome?: 'worked' | "didn't work"
  onDone?: () => void
}) {
  const [outcomeType, setOutcomeType] = useState<'worked' | "didn't work">(defaultOutcome)
  const [note, setNote] = useState('')
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const handleSave = async () => {
    setSaving(true)
    setErr(null)
    const combined = note.trim()
      ? `${outcomeType} — ${note.trim()}`
      : outcomeType
    try {
      const csrf = getCsrfToken()
      const res = await fetch('/api/incidents/memory', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scenario_id: scenarioId,
          cause,
          fix,
          outcome: combined.slice(0, 280),
          csrf_token: csrf,
        }),
        credentials: 'same-origin',
      })
      if (res.ok) {
        setSaved(true)
        if (onDone) setTimeout(onDone, 800)
      } else {
        const d = await res.json().catch(() => null)
        setErr(d?.detail || 'Failed to record outcome.')
      }
    } catch {
      setErr('Network error saving incident memory.')
    } finally {
      setSaving(false)
    }
  }

  if (saved) {
    return (
      <Card data-testid="outcome-saved-banner" className="mt-6 border-ok/30 bg-ok/10 p-4 text-center text-ok">
        <div className="flex items-center justify-center gap-2 text-[14px] font-semibold">
          <Icon name="check" size={16} /> Recorded in team memory
        </div>
        <p className="mt-1 text-[12.5px] text-mute">
          Future investigations will reference this incident resolution when searching past incidents.
        </p>
      </Card>
    )
  }

  return (
    <Card data-testid="record-outcome-card" className="mt-6 p-5 text-left border-line bg-panel">
      <div className="flex items-center gap-2 text-ink">
        <Icon name="history" size={16} className="text-accent" />
        <span className="text-[14px] font-semibold">Record outcome for team memory</span>
      </div>
      <p className="mt-1 text-[12.5px] text-mute">
        One-line note saved for your team. Past incident search will surface this outcome.
      </p>

      {err && (
        <div className="mt-3 text-[12.5px] text-bad">
          {err}
        </div>
      )}

      <div className="mt-3 flex items-center gap-2">
        <button
          type="button"
          onClick={() => setOutcomeType('worked')}
          className={`flex-1 rounded-xl py-2 text-[13px] font-semibold border transition-colors ${
            outcomeType === 'worked'
              ? 'border-ok/60 bg-ok/15 text-ok'
              : 'border-line text-mute hover:bg-panel-2'
          }`}
        >
          ✓ Worked
        </button>
        <button
          type="button"
          onClick={() => setOutcomeType("didn't work")}
          className={`flex-1 rounded-xl py-2 text-[13px] font-semibold border transition-colors ${
            outcomeType === "didn't work"
              ? 'border-bad/60 bg-bad/15 text-bad'
              : 'border-line text-mute hover:bg-panel-2'
          }`}
        >
          ✕ Didn't work
        </button>
      </div>

      <div className="mt-3">
        <input
          data-testid="outcome-note-input"
          value={note}
          maxLength={240}
          onChange={(e) => setNote(e.target.value)}
          placeholder="One-line detail (e.g. latency returned to baseline in 45s)"
          className="h-10 w-full rounded-xl border border-line bg-bg px-3 text-[13px] outline-none placeholder:text-faint focus:border-accent/60"
        />
      </div>

      <div className="mt-3 flex justify-end">
        <PrimaryButton
          data-testid="save-outcome-btn"
          disabled={saving}
          onClick={handleSave}
          icon="check"
          className="h-10 text-[13px] px-4"
        >
          {saving ? 'Saving…' : 'Save outcome'}
        </PrimaryButton>
      </div>
    </Card>
  )
}
