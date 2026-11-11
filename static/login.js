/**
 * OnCall Rehearsal Agent — Login page script
 *
 * Security notes:
 * - All text is set via textContent, never innerHTML (XSS prevention)
 * - CSRF token read from cookie, never from DOM innerHTML
 * - Form submits as standard HTML form POST to avoid JSON fetch complexity
 *   (the POST /login endpoint accepts both; here we use form encoding)
 * - Error messages shown via textContent
 */

'use strict';

(function () {
  // ── Static text (textContent only) ───────────────────────────────────────
  document.querySelector('.sim-banner').textContent = '⚠️  SIMULATED ENVIRONMENT — All data is fictional';
  document.querySelector('.auth-title').textContent = 'OnCall Rehearsal Agent';
  document.querySelector('.auth-subtitle').textContent = 'The on-call agent that rehearses the fix before you run it.';
  document.querySelector('label[for="username"]').textContent = 'Username';
  document.querySelector('label[for="password"]').textContent = 'Password';
  document.getElementById('btn-text').textContent = 'Sign In';

  // ── CSRF: read from cookie ─────────────────────────────────────────────
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

  function populateCsrfToken() {
    const token = getCookie('csrf_token');
    const field = document.getElementById('csrf_token');
    if (field) {
      field.value = token;
    }
  }

  // ── Error display ──────────────────────────────────────────────────────
  function showError(message) {
    const box = document.getElementById('error-box');
    box.textContent = message; // textContent — no XSS risk
    box.classList.remove('hidden');
  }

  function clearError() {
    const box = document.getElementById('error-box');
    box.textContent = '';
    box.classList.add('hidden');
  }

  // ── Form submit ────────────────────────────────────────────────────────
  const form = document.getElementById('login-form');
  const btn = document.getElementById('login-btn');
  const btnText = document.getElementById('btn-text');
  const spinner = document.getElementById('btn-spinner');

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    clearError();

    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;
    const csrfToken = document.getElementById('csrf_token').value;

    // Client-side validation (server always validates too)
    if (!username) {
      showError('Username is required.');
      return;
    }
    if (!password) {
      showError('Password is required.');
      return;
    }
    if (!csrfToken) {
      showError('CSRF token missing. Please refresh the page and try again.');
      return;
    }

    // Show loading state
    btn.disabled = true;
    btnText.textContent = 'Signing in…';
    spinner.classList.remove('hidden');

    // Submit via fetch (JSON) so we can handle errors gracefully
    fetch('/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        username: username,
        password: password,
        csrf_token: csrfToken,
      }),
      credentials: 'same-origin',
    })
      .then(function (res) {
        if (res.ok || res.redirected) {
          // Success — follow redirect
          window.location.href = res.url || '/';
        } else {
          return res.json().then(function (data) {
            const msg = (data && data.detail) ? String(data.detail) : 'Invalid credentials.';
            // Generic message — never expose internal details
            showError('Sign in failed. Please check your credentials and try again.');
          });
        }
      })
      .catch(function () {
        showError('Network error. Please try again.');
      })
      .finally(function () {
        btn.disabled = false;
        btnText.textContent = 'Sign In';
        spinner.classList.add('hidden');
        // Refresh CSRF token after any submission attempt
        populateCsrfToken();
      });
  });

  // ── Init ───────────────────────────────────────────────────────────────
  populateCsrfToken();
})();
