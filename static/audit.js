/**
 * OnCall Rehearsal Agent — Dedicated Audit Log Page
 *
 * All text rendered via textContent (Zero innerHTML).
 */

'use strict';

(function () {
  const container = document.getElementById('audit-page-entries');
  const countBadge = document.getElementById('audit-count-badge');

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  fetch('/admin/audit-log', { credentials: 'same-origin' })
    .then(function (res) {
      if (res.status === 401 || res.status === 403) {
        countBadge.textContent = 'Access Denied (Admin role required)';
        throw new Error('Access denied: You must be signed in as an administrator.');
      }
      if (!res.ok) throw new Error('HTTP ' + res.status);
      return res.json();
    })
    .then(function (data) {
      const entries = data.entries || [];
      countBadge.textContent = entries.length + ' entries recorded';
      container.replaceChildren();

      if (entries.length === 0) {
        container.appendChild(el('p', null, 'No audit entries found.'));
        return;
      }

      entries.forEach(function (e) {
        const item = el('div', 'audit-entry');
        const header = el('div', 'audit-header');
        header.appendChild(el('span', 'audit-action', '📌 ' + e.action));
        header.appendChild(el('span', 'audit-time', e.created_at));
        item.appendChild(header);

        const details = el('div', 'audit-details');
        details.textContent = 'User: ' + (e.username || e.user_id || 'anonymous') +
          ' | Target ID: ' + (e.target_id || '—') +
          ' | IP: ' + (e.ip_address || '—') +
          ' | Details: ' + (e.details_json || '{}');
        item.appendChild(details);

        container.appendChild(item);
      });
    })
    .catch(function (err) {
      container.replaceChildren();
      container.appendChild(el('p', 'warning-text', err.message));
    });
})();
