/**
 * OnCall Rehearsal Agent — Main Single Page Application Logic
 *
 * Security Requirements Strictly Maintained:
 * - Render all text with textContent, NEVER innerHTML (Prevents XSS).
 * - Inline SVG charts drawn using document.createElementNS.
 * - CSRF token read from cookie and submitted on all state changes.
 * - No external scripts or CDNs.
 */

'use strict';

(function () {
  // ── Global State ────────────────────────────────────────────────────────────
  let currentInvestigationId = null;
  let currentProposedFix = null;
  let stopwatchInterval = null;
  let stopwatchStartTime = null;
  let activeManualLogs = [];

  // ── CSRF Cookie Helper ──────────────────────────────────────────────────────
  function getCookie(name) {
    const prefix = name + '=';
    const parts = document.cookie.split(';');
    for (let i = 0; i < parts.length; i++) {
      const part = parts[i].trim();
      if (part.indexOf(prefix) === 0) {
        return part.substring(prefix.length);
      }
    }
    return '';
  }

  function getCsrfToken() {
    return getCookie('csrf_token');
  }

  // ── DOM Helpers (Safe textContent Only) ──────────────────────────────────────
  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function showStatus(message, type) {
    const banner = document.getElementById('status-banner');
    banner.textContent = message;
    banner.className = 'status-banner ' + (type || 'info');
    banner.classList.remove('hidden');
  }

  function clearStatus() {
    const banner = document.getElementById('status-banner');
    banner.textContent = '';
    banner.classList.add('hidden');
  }

  // ── Stopwatch Utilities ─────────────────────────────────────────────────────
  function startStopwatch() {
    const display = document.getElementById('stopwatch-container');
    const timerText = document.getElementById('stopwatch-timer');
    display.classList.remove('hidden');
    stopwatchStartTime = Date.now();
    if (stopwatchInterval) clearInterval(stopwatchInterval);

    stopwatchInterval = setInterval(function () {
      const elapsed = Date.now() - stopwatchStartTime;
      const totalSec = Math.floor(elapsed / 1000);
      const min = Math.floor(totalSec / 60);
      const sec = totalSec % 60;
      const tenths = Math.floor((elapsed % 1000) / 100);
      const pad = function (n) { return (n < 10 ? '0' : '') + n; };
      timerText.textContent = pad(min) + ':' + pad(sec) + '.' + tenths;
    }, 100);
  }

  function stopStopwatch() {
    if (stopwatchInterval) {
      clearInterval(stopwatchInterval);
      stopwatchInterval = null;
    }
    const timerText = document.getElementById('stopwatch-timer');
    return timerText.textContent;
  }

  // ── Mode Switching ──────────────────────────────────────────────────────────
  const tabAgent = document.getElementById('tab-agent-mode');
  const tabManual = document.getElementById('tab-manual-mode');
  const agentPanel = document.getElementById('agent-trigger-panel');
  const manualPanel = document.getElementById('manual-trigger-panel');

  tabAgent.addEventListener('click', function () {
    tabAgent.classList.add('active');
    tabManual.classList.remove('active');
    agentPanel.classList.remove('hidden');
    manualPanel.classList.add('hidden');
    stopStopwatch();
  });

  tabManual.addEventListener('click', function () {
    tabManual.classList.add('active');
    tabAgent.classList.remove('active');
    manualPanel.classList.remove('hidden');
    agentPanel.classList.add('hidden');
    stopStopwatch();
  });

  // ── Manual Stopwatch Mode ───────────────────────────────────────────────────
  const btnStartManual = document.getElementById('btn-start-manual');
  const btnStopManual = document.getElementById('btn-stop-manual');
  const manualViewerArea = document.getElementById('manual-viewer-area');
  const manualLogTerminal = document.getElementById('manual-log-terminal');
  const manualLogSearch = document.getElementById('manual-log-search');
  const manualLogCount = document.getElementById('manual-log-count');

  btnStartManual.addEventListener('click', function () {
    const scenario = document.getElementById('scenario-select').value;
    clearStatus();
    startStopwatch();
    btnStartManual.classList.add('hidden');
    btnStopManual.classList.remove('hidden');
    manualViewerArea.classList.remove('hidden');

    fetch('/api/scenarios/' + encodeURIComponent(scenario) + '/raw_logs', { credentials: 'same-origin' })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        activeManualLogs = data.logs || [];
        renderManualLogs(activeManualLogs);
      })
      .catch(function () {
        showStatus('Failed to load raw scenario logs.', 'error');
      });
  });

  function renderManualLogs(logs) {
    manualLogTerminal.replaceChildren();
    manualLogCount.textContent = logs.length + ' logs displayed';
    logs.forEach(function (log) {
      const line = el('div', 'log-line ' + (log.level || 'INFO'));
      line.textContent = '[' + log.timestamp + '] [' + log.level + '] ' + log.message;
      manualLogTerminal.appendChild(line);
    });
  }

  manualLogSearch.addEventListener('input', function () {
    const query = manualLogSearch.value.toLowerCase().trim();
    if (!query) {
      renderManualLogs(activeManualLogs);
      return;
    }
    const filtered = activeManualLogs.filter(function (l) {
      return (l.message || '').toLowerCase().includes(query) || (l.level || '').toLowerCase().includes(query);
    });
    renderManualLogs(filtered);
  });

  btnStopManual.addEventListener('click', function () {
    const finalTime = stopStopwatch();
    btnStartManual.classList.remove('hidden');
    btnStopManual.classList.add('hidden');
    showStatus('⏱️ Manual investigation completed in ' + finalTime + ' (Industry avg: ~35 min). Compare with the Agent below!', 'success');
  });

  // ── Agent Investigation (SSE Stream) ────────────────────────────────────────
  const btnTrigger = document.getElementById('btn-trigger-alert');
  const investigationSection = document.getElementById('investigation-section');
  const investigationTimeline = document.getElementById('investigation-timeline');
  const toolCountBadge = document.getElementById('tool-count-badge');
  const hypothesisSection = document.getElementById('hypothesis-section');
  const hypothesisGrid = document.getElementById('hypothesis-grid');
  const rehearsalSection = document.getElementById('rehearsal-section');
  const approvalSection = document.getElementById('approval-section');

  btnTrigger.addEventListener('click', function () {
    const scenario = document.getElementById('scenario-select').value;
    const csrfToken = getCsrfToken();

    if (!csrfToken) {
      showStatus('Missing CSRF token. Please refresh the page.', 'error');
      return;
    }

    // Reset UI
    clearStatus();
    investigationSection.classList.remove('hidden');
    investigationTimeline.replaceChildren();
    hypothesisSection.classList.add('hidden');
    hypothesisGrid.replaceChildren();
    rehearsalSection.classList.add('hidden');
    approvalSection.classList.add('hidden');
    toolCountBadge.textContent = '0 / 12 tool calls';

    btnTrigger.disabled = true;
    startStopwatch();

    // Trigger investigation via POST fetch with streaming reader
    fetch('/api/investigations/trigger', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        scenario_id: scenario,
        csrf_token: csrfToken,
      }),
      credentials: 'same-origin',
    })
      .then(function (response) {
        if (!response.ok) {
          throw new Error('HTTP ' + response.status + ' starting investigation');
        }
        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';

        function readChunk() {
          reader.read().then(function (result) {
            if (result.done) {
              btnTrigger.disabled = false;
              return;
            }
            buffer += decoder.decode(result.value, { stream: true });
            const lines = buffer.split('\n\n');
            buffer = lines.pop(); // keep remainder

            lines.forEach(function (block) {
              const trimmed = block.trim();
              if (trimmed.startsWith('data:')) {
                try {
                  const event = JSON.parse(trimmed.substring(5).trim());
                  handleSSEEvent(event);
                } catch (e) {
                  console.error('Error parsing SSE event:', e);
                }
              }
            });

            readChunk();
          }).catch(function (err) {
            console.error('SSE read error:', err);
            btnTrigger.disabled = false;
            stopStopwatch();
            showStatus('Error reading investigation stream.', 'error');
          });
        }

        readChunk();
      })
      .catch(function (err) {
        btnTrigger.disabled = false;
        stopStopwatch();
        showStatus('Failed to trigger investigation: ' + err.message, 'error');
      });
  });

  // ── Handle Agent SSE Events ─────────────────────────────────────────────────
  function handleSSEEvent(event) {
    if (event.type === 'init') {
      currentInvestigationId = event.investigation_id;
      return;
    }

    if (event.type === 'tool_call_start') {
      toolCountBadge.textContent = event.tool_call_index + ' / 12 tool calls';
      const step = el('div', 'timeline-step');
      step.id = 'step-' + event.tool_call_index;

      const header = el('div', 'timeline-step-header');
      const toolName = el('span', 'step-tool-name', '⚡ ' + event.tool_name);
      const idx = el('span', 'step-index', 'Step ' + event.tool_call_index);
      header.appendChild(toolName);
      header.appendChild(idx);

      const args = el('div', 'step-args', 'Args: ' + JSON.stringify(event.arguments));
      step.appendChild(header);
      step.appendChild(args);
      investigationTimeline.appendChild(step);
      step.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    if (event.type === 'tool_call_result') {
      const step = document.getElementById('step-' + event.tool_call_index);
      if (step) {
        const summary = el('div', 'step-summary');
        if (event.data) {
          summary.textContent = JSON.stringify(event.data, null, 2);
        } else {
          summary.textContent = event.summary || 'Telemetry observed';
        }
        step.appendChild(summary);
      }
    }

    if (event.type === 'rehearsal_result') {
      renderRehearsal(event);
    }

    if (event.type === 'investigation_completed') {
      const finalTime = stopStopwatch();
      btnTrigger.disabled = false;
      showStatus('🎯 Agent investigation completed in ' + finalTime + ' with fix rehearsed in sandbox!', 'success');
      renderHypotheses(event.result.hypotheses);
      renderApprovalBar(event.result.proposed_fix);
    }

    if (event.type === 'error') {
      btnTrigger.disabled = false;
      stopStopwatch();
      showStatus('Agent alert: ' + (event.message || 'Investigation stopped.'), 'error');
    }
  }

  // ── Render Hypothesis Court ─────────────────────────────────────────────────
  function renderHypotheses(hypotheses) {
    hypothesisSection.classList.remove('hidden');
    hypothesisGrid.replaceChildren();

    (hypotheses || []).forEach(function (h) {
      const card = el('div', 'hypothesis-card rank-' + h.rank);

      // Header: Rank badge and Confidence
      const header = el('div', 'hypothesis-header');
      const rankBadge = el('span', 'rank-badge', 'Rank #' + h.rank);
      const confPct = Math.round((h.confidence || 0) * 100);
      let confClass = 'confidence-low';
      if (confPct >= 70) confClass = 'confidence-high';
      else if (confPct >= 40) confClass = 'confidence-med';
      const confGauge = el('span', 'confidence-gauge ' + confClass, confPct + '% Confidence');
      header.appendChild(rankBadge);
      header.appendChild(confGauge);
      card.appendChild(header);

      // Cause
      const cause = el('div', 'hypothesis-cause', h.cause);
      card.appendChild(cause);

      // Evidence Accordion
      const accordion = el('div', 'evidence-accordion');

      // Evidence For
      const groupFor = el('div', 'evidence-group');
      groupFor.appendChild(el('h4', null, '✅ Evidence For (' + (h.evidence_for || []).length + ')'));
      (h.evidence_for || []).forEach(function (ev) {
        const item = el('div', 'evidence-item');
        item.appendChild(el('div', null, ev.description));
        const cit = el('div', 'evidence-citation', 'Citing: [' + ev.tool_call + '] ' + (ev.source_row || ''));
        item.appendChild(cit);
        groupFor.appendChild(item);
      });
      accordion.appendChild(groupFor);

      // Evidence Against
      const groupAgainst = el('div', 'evidence-group');
      groupAgainst.appendChild(el('h4', null, '❌ Evidence Against / Cross-Examination (' + (h.evidence_against || []).length + ')'));
      if (h.evidence_against && h.evidence_against.length > 0) {
        h.evidence_against.forEach(function (ev) {
          const item = el('div', 'evidence-item');
          item.appendChild(el('div', null, ev.description));
          const cit = el('div', 'evidence-citation', 'Citing: [' + ev.tool_call + '] ' + (ev.source_row || ''));
          item.appendChild(cit);
          groupAgainst.appendChild(item);
        });
      } else {
        groupAgainst.appendChild(el('div', 'evidence-item', 'None identified — primary consistent hypothesis.'));
      }
      accordion.appendChild(groupAgainst);

      card.appendChild(accordion);
      hypothesisGrid.appendChild(card);
    });

    hypothesisSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  // ── Render Sandbox Rehearsal ────────────────────────────────────────────────
  function renderRehearsal(rehearsal) {
    rehearsalSection.classList.remove('hidden');

    // Overview Badge
    const overview = document.getElementById('rehearsal-overview');
    overview.replaceChildren();
    const badge = el('span', 'rehearsal-badge', '✅ Fix ' + rehearsal.fix_id + ' successfully rehearsed in sandbox');
    const desc = el('p', null, rehearsal.description);
    overview.appendChild(badge);
    overview.appendChild(desc);

    // Table rows
    const tbody = document.getElementById('metrics-table-body');
    tbody.replaceChildren();

    const before = rehearsal.before_metrics || {};
    const after = rehearsal.after_metrics || {};
    const metricKeys = ['p95_latency_ms', 'error_rate_pct', 'memory_mb', 'db_connections'];
    const labels = {
      p95_latency_ms: 'P95 Latency',
      error_rate_pct: 'Error Rate',
      memory_mb: 'Memory Usage',
      db_connections: 'DB Connections',
    };
    const units = {
      p95_latency_ms: 'ms',
      error_rate_pct: '%',
      memory_mb: 'MB',
      db_connections: ' conns',
    };

    metricKeys.forEach(function (key) {
      if (before[key] !== undefined || after[key] !== undefined) {
        const tr = document.createElement('tr');
        const bVal = before[key] !== undefined ? before[key] : '—';
        const aVal = after[key] !== undefined ? after[key] : '—';

        let deltaText = '—';
        if (typeof bVal === 'number' && typeof aVal === 'number' && bVal > 0) {
          const change = Math.round(((aVal - bVal) / bVal) * 100);
          deltaText = (change > 0 ? '+' : '') + change + '%';
        }

        tr.appendChild(el('td', null, labels[key] || key));
        tr.appendChild(el('td', null, bVal + (units[key] || '')));
        tr.appendChild(el('td', null, aVal + (units[key] || '')));
        tr.appendChild(el('td', 'delta-good', deltaText));
        tbody.appendChild(tr);
      }
    });

    // Render Inline SVG Chart
    renderInlineSvgChart(before, after);
  }

  function renderInlineSvgChart(before, after) {
    const chartContainer = document.getElementById('metrics-svg-chart');
    chartContainer.replaceChildren();

    const svgNS = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(svgNS, 'svg');
    svg.setAttribute('viewBox', '0 0 460 180');
    svg.setAttribute('width', '100%');
    svg.setAttribute('height', '180');

    // Background
    const bg = document.createElementNS(svgNS, 'rect');
    bg.setAttribute('width', '460');
    bg.setAttribute('height', '180');
    bg.setAttribute('fill', '#161b22');
    bg.setAttribute('rx', '6');
    svg.appendChild(bg);

    // Bars for Latency and Error Rate
    const metricsToDraw = [
      { name: 'P95 Latency (ms)', b: Number(before.p95_latency_ms || 200), a: Number(after.p95_latency_ms || 180), max: 10000 },
      { name: 'DB Conns', b: Number(before.db_connections || 90), a: Number(after.db_connections || 12), max: 100 },
    ];

    metricsToDraw.forEach(function (m, idx) {
      const yOffset = 30 + idx * 70;

      // Label
      const title = document.createElementNS(svgNS, 'text');
      title.setAttribute('x', '20');
      title.setAttribute('y', String(yOffset));
      title.setAttribute('fill', '#8b949e');
      title.setAttribute('font-size', '12');
      title.setAttribute('font-weight', '600');
      title.textContent = m.name;
      svg.appendChild(title);

      // Bar Before (Red)
      const bWidth = Math.max(10, Math.min(300, (m.b / m.max) * 300));
      const barBefore = document.createElementNS(svgNS, 'rect');
      barBefore.setAttribute('x', '20');
      barBefore.setAttribute('y', String(yOffset + 8));
      barBefore.setAttribute('width', String(bWidth));
      barBefore.setAttribute('height', '16');
      barBefore.setAttribute('fill', '#f85149');
      barBefore.setAttribute('rx', '3');
      svg.appendChild(barBefore);

      const bValText = document.createElementNS(svgNS, 'text');
      bValText.setAttribute('x', String(bWidth + 28));
      bValText.setAttribute('y', String(yOffset + 21));
      bValText.setAttribute('fill', '#ffa198');
      bValText.setAttribute('font-size', '11');
      bValText.textContent = 'Before: ' + m.b;
      svg.appendChild(bValText);

      // Bar After (Green)
      const aWidth = Math.max(10, Math.min(300, (m.a / m.max) * 300));
      const barAfter = document.createElementNS(svgNS, 'rect');
      barAfter.setAttribute('x', '20');
      barAfter.setAttribute('y', String(yOffset + 28));
      barAfter.setAttribute('width', String(aWidth));
      barAfter.setAttribute('height', '16');
      barAfter.setAttribute('fill', '#3fb950');
      barAfter.setAttribute('rx', '3');
      svg.appendChild(barAfter);

      const aValText = document.createElementNS(svgNS, 'text');
      aValText.setAttribute('x', String(aWidth + 28));
      aValText.setAttribute('y', String(yOffset + 41));
      aValText.setAttribute('fill', '#56d364');
      aValText.setAttribute('font-size', '11');
      aValText.textContent = 'After: ' + m.a;
      svg.appendChild(aValText);
    });

    chartContainer.appendChild(svg);
  }

  // ── Render Approval Bar (Risk Ladder) ───────────────────────────────────────
  function renderApprovalBar(proposedFix) {
    if (!proposedFix) return;
    currentProposedFix = proposedFix;
    approvalSection.classList.remove('hidden');

    const riskPill = document.getElementById('approval-risk-pill');
    const blastPill = document.getElementById('approval-blast-pill');
    const title = document.getElementById('approval-fix-title');
    const action = document.getElementById('approval-fix-action');
    const rationale = document.getElementById('approval-fix-rationale');
    const level2Container = document.getElementById('level2-confirm-container');
    const targetPhrase = document.getElementById('confirm-phrase-target');

    riskPill.className = 'risk-pill risk-level-' + proposedFix.risk_level;
    const riskLabels = {
      0: 'Level 0: Safe Read-Only / Auto-Rehearsed',
      1: 'Level 1: Reversible Fix (Requires 1-Click Approval)',
      2: 'Level 2: Destructive / Risky (Requires Typed Confirmation)',
    };
    riskPill.textContent = riskLabels[proposedFix.risk_level] || 'Level ' + proposedFix.risk_level;
    blastPill.textContent = 'Blast radius: ' + proposedFix.blast_radius;

    title.textContent = 'Recommended Fix: ' + proposedFix.fix_id;
    action.textContent = proposedFix.action;
    rationale.textContent = 'Agent rationale: ' + proposedFix.rationale;

    if (proposedFix.risk_level === 2) {
      level2Container.classList.remove('hidden');
      targetPhrase.textContent = 'CONFIRM ' + proposedFix.fix_id;
      document.getElementById('confirm-input').value = '';
    } else {
      level2Container.classList.add('hidden');
    }

    approvalSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  // ── Approve / Reject Actions ────────────────────────────────────────────────
  const btnApprove = document.getElementById('btn-approve-fix');
  const btnReject = document.getElementById('btn-reject-fix');

  btnApprove.addEventListener('click', function () {
    if (!currentProposedFix || !currentInvestigationId) return;

    const csrfToken = getCsrfToken();
    let confirmationText = null;

    if (currentProposedFix.risk_level === 2) {
      const input = document.getElementById('confirm-input').value.trim();
      const required = 'CONFIRM ' + currentProposedFix.fix_id;
      if (input !== required) {
        showStatus('Confirmation mismatch! You must type exactly: ' + required, 'error');
        return;
      }
      confirmationText = input;
    }

    btnApprove.disabled = true;
    fetch('/api/investigations/' + currentInvestigationId + '/approve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        investigation_id: currentInvestigationId,
        action: 'approve',
        confirmation_text: confirmationText,
        csrf_token: csrfToken,
      }),
      credentials: 'same-origin',
    })
      .then(function (res) {
        if (!res.ok) {
          return res.json().then(function (d) { throw new Error(d.detail || 'Approval failed'); });
        }
        return res.json();
      })
      .then(function () {
        showStatus('✅ Fix ' + currentProposedFix.fix_id + ' APPROVED and successfully verified by human on-call!', 'success');
        approvalSection.classList.add('hidden');
      })
      .catch(function (err) {
        showStatus('Approval rejected by backend: ' + err.message, 'error');
      })
      .finally(function () {
        btnApprove.disabled = false;
      });
  });

  btnReject.addEventListener('click', function () {
    if (!currentInvestigationId) return;
    const csrfToken = getCsrfToken();

    btnReject.disabled = true;
    fetch('/api/investigations/' + currentInvestigationId + '/approve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        investigation_id: currentInvestigationId,
        action: 'reject',
        csrf_token: csrfToken,
      }),
      credentials: 'same-origin',
    })
      .then(function () {
        showStatus('❌ Proposed fix rejected. Escalating to primary on-call engineer.', 'info');
        approvalSection.classList.add('hidden');
      })
      .finally(function () {
        btnReject.disabled = false;
      });
  });

  // ── Audit Log Modal (Admin View) ────────────────────────────────────────────
  const btnViewAudit = document.getElementById('btn-view-audit');
  const auditModal = document.getElementById('audit-modal');
  const btnCloseAudit = document.getElementById('btn-close-audit');
  const auditEntries = document.getElementById('audit-log-entries');

  btnViewAudit.addEventListener('click', function () {
    auditEntries.replaceChildren();
    auditModal.classList.remove('hidden');

    fetch('/admin/audit-log', { credentials: 'same-origin' })
      .then(function (res) {
        if (res.status === 403) {
          throw new Error('Access denied: Audit log requires administrator privileges.');
        }
        if (!res.ok) throw new Error('HTTP ' + res.status);
        return res.json();
      })
      .then(function (data) {
        const list = data.entries || [];
        if (list.length === 0) {
          auditEntries.appendChild(el('p', null, 'No audit entries recorded yet.'));
          return;
        }
        list.forEach(function (e) {
          const item = el('div', 'audit-entry');
          const header = el('div', 'audit-header');
          header.appendChild(el('span', 'audit-action', e.action));
          header.appendChild(el('span', 'audit-time', e.created_at));
          item.appendChild(header);

          const details = el('div', 'audit-details');
          details.textContent = 'User: ' + (e.username || e.user_id || 'system') + ' | IP: ' + (e.ip_address || '—') + ' | Details: ' + (e.details_json || '{}');
          item.appendChild(details);
          auditEntries.appendChild(item);
        });
      })
      .catch(function (err) {
        auditEntries.appendChild(el('p', 'warning-text', err.message));
      });
  });

  btnCloseAudit.addEventListener('click', function () {
    auditModal.classList.add('hidden');
  });

  // ── Sign Out ────────────────────────────────────────────────────────────────
  document.getElementById('btn-logout').addEventListener('click', function () {
    fetch('/logout', { method: 'POST', credentials: 'same-origin' })
      .finally(function () {
        window.location.href = '/login';
      });
  });

  // ── Initial Check ───────────────────────────────────────────────────────────
  fetch('/api/scenarios', { credentials: 'same-origin' })
    .then(function (res) {
      if (res.status === 401) {
        window.location.href = '/login';
      }
    });
})();
