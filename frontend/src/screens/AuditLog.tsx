/**
 * Phase 11 — Security & System Audit Log Screen (Admin only)
 *
 * Features:
 *  - Real-time audit log table from /admin/audit-log
 *  - Action and text filters
 *  - Expandable row details (JSON/formatted)
 *  - Explicit states for: loading, empty, forbidden (403), rate-limited (429)
 */
import { useEffect, useState } from 'react'
import { Shell } from '../components/Frame'
import { Icon } from '../components/Icon'
import { Card, Chip, GhostButton, Label, PageHeader } from '../components/ui'
import { useNav } from '../nav'

interface AuditEntry {
  id: number
  user_id: number | null
  username?: string | null
  action: string
  target_id: string | null
  details_json: string | null
  ip_address: string | null
  created_at: string
}

export function AuditLog() {
  const { go } = useNav()
  const [entries, setEntries] = useState<AuditEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [errorStatus, setErrorStatus] = useState<'forbidden' | 'rate-limited' | 'error' | null>(null)
  const [expandedId, setExpandedId] = useState<number | null>(null)
  const [filterAction, setFilterAction] = useState<string>('all')
  const [searchTerm, setSearchTerm] = useState<string>('')

  const fetchLogs = async () => {
    setLoading(true)
    setErrorStatus(null)
    try {
      const res = await fetch('/admin/audit-log?limit=100', { credentials: 'same-origin' })
      if (res.status === 403) {
        setErrorStatus('forbidden')
        return
      }
      if (res.status === 429) {
        setErrorStatus('rate-limited')
        return
      }
      if (!res.ok) {
        setErrorStatus('error')
        return
      }
      const data = await res.json()
      setEntries(data.entries || [])
    } catch {
      setErrorStatus('error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchLogs()
  }, [])

  const actions = Array.from(new Set(entries.map((e) => e.action))).sort()

  const filteredEntries = entries.filter((e) => {
    if (filterAction !== 'all' && e.action !== filterAction) return false
    if (!searchTerm.trim()) return true
    const term = searchTerm.toLowerCase()
    return (
      e.action.toLowerCase().includes(term) ||
      (e.target_id || '').toLowerCase().includes(term) ||
      (e.username || '').toLowerCase().includes(term) ||
      (e.details_json || '').toLowerCase().includes(term) ||
      (e.ip_address || '').toLowerCase().includes(term)
    )
  })

  return (
    <Shell
      current={-1}
      footer={
        <div className="flex items-center justify-between gap-4 px-5 py-3">
          <GhostButton onClick={() => go('alert')}>
            <Icon name="arrow-left" size={16} className="mr-1.5" />
            Back to incidents
          </GhostButton>
          <GhostButton onClick={fetchLogs} disabled={loading}>
            <Icon name="clock" size={16} className="mr-1.5" />
            Refresh
          </GhostButton>
        </div>
      }
    >
      <PageHeader
        eyebrow="Security &amp; Governance"
        title="Audit Log"
        sub="Immutable record of system actions, fix approvals, escalations, and neutralized security events."
      />

      {/* ── Forbidden (403) State ── */}
      {errorStatus === 'forbidden' && (
        <Card data-testid="audit-forbidden-state" className="border-bad/40 bg-bad/5 p-8 text-center">
          <div className="mx-auto grid size-12 place-items-center rounded-full bg-bad/15 text-bad">
            <Icon name="shield" size={24} />
          </div>
          <h2 className="mt-4 text-[18px] font-semibold text-ink">Access Denied</h2>
          <p className="mt-2 text-[14px] text-mute max-w-md mx-auto">
            You do not have administrator privileges to view the security audit log.
            Contact an administrator if you require access.
          </p>
        </Card>
      )}

      {/* ── Rate Limited (429) State ── */}
      {errorStatus === 'rate-limited' && (
        <Card data-testid="audit-rate-limited-state" className="border-warn/40 bg-warn/5 p-8 text-center">
          <div className="mx-auto grid size-12 place-items-center rounded-full bg-warn/15 text-warn">
            <Icon name="alert" size={24} />
          </div>
          <h2 className="mt-4 text-[18px] font-semibold text-ink">Rate Limit Exceeded</h2>
          <p className="mt-2 text-[14px] text-mute max-w-md mx-auto">
            Too many requests to the audit API. Please wait a moment before refreshing.
          </p>
          <div className="mt-5">
            <GhostButton onClick={fetchLogs}>Try again</GhostButton>
          </div>
        </Card>
      )}

      {/* ── General Error State ── */}
      {errorStatus === 'error' && (
        <Card className="border-bad/30 p-6 text-center text-bad">
          <p className="text-[14px]">Failed to retrieve audit log entries. Please check your connection and retry.</p>
        </Card>
      )}

      {/* ── Normal State: Controls and Table ── */}
      {!errorStatus && (
        <div className="space-y-4">
          {/* Filter Bar */}
          <div className="flex flex-wrap items-center gap-3">
            <div className="relative flex-1 min-w-[200px]">
              <Icon
                name="search"
                size={15}
                className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-mute"
              />
              <input
                data-testid="audit-search-filter"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Search action, target, user, details…"
                className="h-10 w-full rounded-xl border border-line bg-bg pl-9 pr-4 text-[13.5px] outline-none placeholder:text-faint focus:border-accent/60"
              />
            </div>

            <select
              data-testid="audit-action-filter"
              value={filterAction}
              onChange={(e) => setFilterAction(e.target.value)}
              className="h-10 rounded-xl border border-line bg-bg px-3 text-[13px] text-ink outline-none"
            >
              <option value="all">All actions ({entries.length})</option>
              {actions.map((act) => (
                <option key={act} value={act}>
                  {act} ({entries.filter((e) => e.action === act).length})
                </option>
              ))}
            </select>

            {(searchTerm || filterAction !== 'all') && (
              <GhostButton
                onClick={() => {
                  setSearchTerm('')
                  setFilterAction('all')
                }}
              >
                Clear
              </GhostButton>
            )}
          </div>

          {/* Table Container */}
          <Card className="overflow-hidden p-0">
            {loading ? (
              <div data-testid="audit-loading-state" className="flex items-center justify-center gap-2.5 py-16 text-mute text-[14px]">
                <Icon name="loader" size={20} className="animate-spin text-accent" />
                Loading audit log records…
              </div>
            ) : filteredEntries.length === 0 ? (
              <div data-testid="audit-empty-state" className="py-16 text-center">
                <div className="mx-auto grid size-10 place-items-center rounded-full bg-panel-2 text-mute">
                  <Icon name="logs" size={20} />
                </div>
                <p className="mt-3 text-[14.5px] font-medium text-ink">No audit entries found</p>
                <p className="mt-1 text-[13px] text-mute">No records match the current filter criteria.</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-[13px]">
                  <thead className="border-b border-line bg-panel-2/50 text-[11.5px] font-semibold uppercase tracking-wider text-mute">
                    <tr>
                      <th className="px-4 py-3">Timestamp</th>
                      <th className="px-4 py-3">Action</th>
                      <th className="px-4 py-3">User</th>
                      <th className="px-4 py-3">Target</th>
                      <th className="px-4 py-3">IP Address</th>
                      <th className="px-4 py-3 text-right">Details</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line/60">
                    {filteredEntries.map((row) => {
                      const isExpanded = expandedId === row.id
                      const isSecurityEvent =
                        row.action.includes('blocked') ||
                        row.action.includes('escalate') ||
                        row.action.includes('lock')
                      return (
                        <tr
                          key={row.id}
                          className="group cursor-pointer hover:bg-panel-2/30 transition-colors"
                          onClick={() => setExpandedId(isExpanded ? null : row.id)}
                        >
                          <td className="px-4 py-3 whitespace-nowrap font-mono text-[12px] text-faint">
                            {row.created_at.slice(0, 19).replace('T', ' ')}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap">
                            <span
                              className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11.5px] font-semibold ${
                                isSecurityEvent
                                  ? 'bg-warn/15 text-warn'
                                  : row.action.includes('approved')
                                  ? 'bg-ok/15 text-ok'
                                  : 'bg-accent/15 text-accent'
                              }`}
                            >
                              {row.action}
                            </span>
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-ink/90 font-medium">
                            {row.username || (row.user_id ? `User #${row.user_id}` : 'system')}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap font-mono text-[12px] text-mute">
                            {row.target_id || '—'}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap font-mono text-[12px] text-faint">
                            {row.ip_address || '—'}
                          </td>
                          <td className="px-4 py-3 text-right">
                            <button
                              type="button"
                              aria-label={isExpanded ? 'Collapse row details' : 'Expand row details'}
                              className="text-mute hover:text-ink text-[12px]"
                            >
                              {isExpanded ? 'Hide' : 'View'}
                            </button>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          {/* Expanded Detail Panel */}
          {expandedId && (
            <Card className="p-4 border-accent/30 bg-bg/70">
              {(() => {
                const target = entries.find((e) => e.id === expandedId)
                if (!target) return null
                let formatted = target.details_json
                try {
                  if (target.details_json) {
                    formatted = JSON.stringify(JSON.parse(target.details_json), null, 2)
                  }
                } catch {
                  // Keep as string
                }
                return (
                  <div>
                    <div className="flex items-center justify-between pb-2 border-b border-line mb-3">
                      <Label>Record #{target.id} — {target.action}</Label>
                      <button
                        type="button"
                        onClick={() => setExpandedId(null)}
                        className="text-[12px] text-mute hover:text-ink"
                      >
                        Close
                      </button>
                    </div>
                    <pre className="overflow-x-auto rounded-lg border border-line bg-panel p-3 font-mono text-[12px] text-ink/90 leading-relaxed">
                      {formatted || 'No additional details logged.'}
                    </pre>
                  </div>
                )
              })()}
            </Card>
          )}

          {!loading && (
            <p className="text-right text-[12px] text-faint">
              Showing {filteredEntries.length} of {entries.length} records
            </p>
          )}
        </div>
      )}
    </Shell>
  )
}
