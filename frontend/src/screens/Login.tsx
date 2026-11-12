import { useState } from 'react'
import { Icon, Logo } from '../components/Icon'
import { getCsrfToken, useNav } from '../nav'

export function Login() {
  const { go, setCurrentUser } = useNav()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setErrorMsg(null)

    if (!username.trim() || !password) {
      setErrorMsg('Please enter both username and password.')
      return
    }

    setLoading(true)
    try {
      let csrfToken = getCsrfToken()

      // If no CSRF token yet, fetch /login once to set the cookie
      if (!csrfToken) {
        await fetch('/login', { credentials: 'same-origin' })
        csrfToken = getCsrfToken()
      }

      const res = await fetch('/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: username.trim(),
          password,
          csrf_token: csrfToken,
        }),
        credentials: 'same-origin',
      })

      if (res.ok || res.redirected) {
        // Fetch current user details if available
        try {
          const meRes = await fetch('/api/me', { credentials: 'same-origin' })
          if (meRes.ok) {
            const meData = await meRes.json()
            setCurrentUser(meData)
          } else {
            setCurrentUser({ username: username.trim(), role: 'Engineer' })
          }
        } catch {
          setCurrentUser({ username: username.trim(), role: 'Engineer' })
        }
        go('alert')
      } else {
        const data = await res.json().catch(() => null)
        const detail = data?.detail || "That username or password doesn't match. Check them and try again."
        setErrorMsg(typeof detail === 'string' ? detail : "That username or password doesn't match. Check them and try again.")
      }
    } catch {
      setErrorMsg('Network error. Unable to connect to server.')
    } finally {
      setLoading(false)
    }
  }

  const hasError = Boolean(errorMsg)

  return (
    <div className="relative flex h-full flex-col overflow-y-auto bg-bg">
      <div className="pointer-events-none absolute left-1/2 top-[-12rem] aspect-square w-[120%] max-w-[34rem] -translate-x-1/2 rounded-full bg-accent/[0.09] blur-[110px]" />
      <div className="screen-in relative m-auto flex w-full max-w-md flex-col items-center px-4 py-10">
        <Logo size={52} />
        <h1 className="mt-6 text-center text-[26px] font-semibold tracking-tight @tablet:text-[30px]">
          OnCall Rehearsal Agent
        </h1>
        <p className="mt-2 text-center text-[15px] text-mute">
          Sign in to see what happened and what to do next.
        </p>

        <form
          className="mt-8 w-full space-y-5 rounded-3xl border border-line bg-panel p-6 @tablet:p-8"
          onSubmit={handleSubmit}
        >
          {hasError && (
            <div
              role="alert"
              className="flex items-start gap-3 rounded-xl border border-bad/30 bg-bad/10 px-4 py-3 text-[13.5px] leading-snug text-bad"
            >
              <Icon name="info" size={18} className="mt-px shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}

          <label className="block">
            <span className="mb-2 block text-[13px] font-medium text-ink/90">Username</span>
            <span
              className={`flex h-12 items-center gap-3 rounded-xl border bg-bg px-4 focus-within:ring-4 ${
                hasError
                  ? 'border-bad/60 text-bad focus-within:ring-bad/10'
                  : 'border-line text-mute focus-within:border-accent/60 focus-within:ring-accent/10'
              }`}
            >
              <Icon name="user" size={18} />
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="maya.reyes"
                aria-invalid={hasError}
                autoComplete="username"
                required
                className="h-full min-w-0 flex-1 bg-transparent text-[15px] text-ink outline-none placeholder:text-faint"
              />
            </span>
          </label>

          <label className="block">
            <span className="mb-2 block text-[13px] font-medium text-ink/90">Password</span>
            <span
              className={`flex h-12 items-center gap-3 rounded-xl border bg-bg px-4 focus-within:ring-4 ${
                hasError
                  ? 'border-bad/60 text-bad focus-within:ring-bad/10'
                  : 'border-line text-mute focus-within:border-accent/60 focus-within:ring-accent/10'
              }`}
            >
              <Icon name="lock" size={18} />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter your password"
                aria-invalid={hasError}
                autoComplete="current-password"
                required
                className="h-full min-w-0 flex-1 bg-transparent text-[15px] text-ink outline-none placeholder:text-faint"
              />
            </span>
          </label>

          <button
            type="submit"
            disabled={loading}
            className="flex h-12 w-full items-center justify-center rounded-xl bg-accent text-[15px] font-semibold text-bg shadow-[0_10px_28px_-10px_rgba(139,147,255,0.9)] hover:bg-accent-strong disabled:opacity-60"
          >
            {loading ? 'Signing in…' : 'Sign In'}
          </button>
        </form>

        <div className="mt-7 flex items-center gap-2.5 text-[13px] text-mute">
          <Icon name="shield" size={16} className="text-accent" />
          The agent investigates. You decide.
        </div>
      </div>
    </div>
  )
}
