# OnCall Rehearsal Agent — Render Deployment

> Deploy as a Docker web service. No local Docker required; Render builds the
> image from your repository using the existing `Dockerfile`.

---

## Honest Limitations (read first)

### What resets on every redeploy

| Data | Fate |
|---|---|
| SQLite database (`oncall.db`) | **Wiped** — ephemeral disk, starts empty |
| All user accounts | **Lost** — admin re-created automatically from env vars (see below) |
| All sessions | **Lost** — everyone is logged out |
| Audit log | **Lost** |

### What happens when the free service sleeps

Render's free plan spins down any service that has received no HTTP traffic for
**15 minutes**. When the container is terminated:

- The SQLite database is **also wiped** (it lives on the container's ephemeral filesystem).
- The admin account is **re-created on the next cold start** from `ADMIN_USERNAME`
  and `ADMIN_PASSWORD` env vars — no manual action needed.
- The first request after sleep takes **30–60 seconds** while Render starts a new
  container. Subsequent requests are fast.

> **Bottom line**: treat this deployment as a stateless demo tool. Data does not
> persist across sleeps or deploys. If you need persistence, upgrade to a paid
> Render plan with a persistent disk or add a PostgreSQL database.

---

## Step 1 — Connect your repository

1. Go to [dashboard.render.com](https://dashboard.render.com) → **New** → **Web Service**.
2. Connect your GitHub/GitLab account and select the `AgentX` repository.
3. Render will detect `render.yaml` and pre-fill the service settings.

---

## Step 2 — Set secret environment variables in the dashboard

The four variables below have `sync: false` in `render.yaml`, which means Render
will **not** read their values from the file — you must type them yourself in the
Render dashboard. This keeps secrets out of your repository.

Go to your service → **Environment** tab, then set:

| Variable | What to put |
|---|---|
| `ANTHROPIC_API_KEY` | Your Anthropic API key (`sk-ant-...`) |
| `SECRET_KEY` | A random string ≥ 32 chars. Generate one: `openssl rand -base64 32` |
| `ADMIN_USERNAME` | The username you will log in with (e.g. `admin`) |
| `ADMIN_PASSWORD` | A strong password, ≥ 12 chars with uppercase, digit, and symbol |

> **`CORS_ORIGIN`** also has `sync: false` but you need the service URL to fill
> it in — see Step 3.

**Non-secret variables are pre-set in `render.yaml`** and do not need dashboard input:
`PRODUCTION=true`, `AGENT_MODE=live`, `CLAUDE_MODEL=claude-sonnet-4-5`,
`DATABASE_URL=sqlite:///./oncall.db`, `LOG_LEVEL=INFO`.

---

## Step 3 — Deploy, then fix CORS_ORIGIN (two-step)

This is a chicken-and-egg problem: `CORS_ORIGIN` must be your service URL, but
the URL is only known after the first deploy.

**First deploy**: click **Deploy**. Render builds the Docker image from source
(3–5 min). The service starts with `CORS_ORIGIN` unset, which defaults to
`http://localhost:8000` and will cause CORS errors if you try to log in.

**After the first deploy**:
1. Copy the `.onrender.com` URL from the top of your service page.
2. Go to **Environment** → find `CORS_ORIGIN` → click **Edit** → paste the URL
   (e.g. `https://oncall-agent.onrender.com`).
3. Click **Save Changes** — Render automatically triggers a second deploy
   (~30 seconds). After it completes, the app is fully functional.

---

## Step 4 — Verify the health endpoint

```
https://<your-service>.onrender.com/health
```

Expected response:

```json
{"status": "ok"}
```

---

## Post-Deploy Verification Checklist

Work through these in a real browser once the second deploy (Step 3) completes:

| # | Action | Expected result |
|---|---|---|
| 1 | Open your Render URL | Login page loads, no console errors |
| 2 | Enter a wrong password | Red "Invalid credentials" alert appears |
| 3 | Log in with `ADMIN_USERNAME` / `ADMIN_PASSWORD` | Alert screen loads with "Start investigation" |
| 4 | Select any scenario → Start investigation | SSE stream opens; four tool checks appear one by one; screen auto-advances to "likely causes" |
| 5 | Advance through Theories → Fix → Decision | Each screen loads; practice run shows before/after metrics |
| 6 | Approve a Level 1 fix | "Fix approved and applied" success screen |
| 7 | Open user menu → View profile | Username and role shown |
| 8 | Sign out | Redirected to login; back-button does not expose protected screen |
| 9 | Check Render **Logs** tab | Startup line: `Admin user 'admin' created from ADMIN_USERNAME/ADMIN_PASSWORD env vars.` |

---

## Switching to mock mode (no Anthropic API spend)

In the Render dashboard → **Environment** → change `AGENT_MODE` from `live` to `mock`.
Save and redeploy. The investigation stream runs deterministically against the
scenario data files with no API calls. Change back to `live` when done.

---

## Teardown

1. Render dashboard → your service → **Settings** → scroll to the bottom →
   **Delete Service** → type the service name to confirm.

2. That's all Render needs. No other cloud resources are created.

> If you also want to remove the GitHub/GitLab connection, go to your Render
> account **Settings** → **Connected Accounts** → revoke access.

---

## FAQ

**Why does the app bind to `$PORT` and not `8080`?**
The `Dockerfile` CMD hardcodes `--port 8080`, but Render injects a different port
via the `PORT` environment variable. The `dockerCommand` in `render.yaml` overrides
the Dockerfile CMD with `--port $PORT` so the server always binds to the port
Render expects. Without this override, Render's health checks would fail and the
service would never become healthy.

**Can I use a custom domain?**
Yes — Render dashboard → **Settings** → **Custom Domains**. Free plan supports
custom domains with auto-provisioned TLS.

**Why no persistent disk?**
Render's persistent disk requires a paid plan. For a training tool used in short
sessions, ephemeral SQLite is acceptable. If you upgrade, add a persistent disk
mounted at `/data` and change `DATABASE_URL` to `sqlite:////data/oncall.db`.
