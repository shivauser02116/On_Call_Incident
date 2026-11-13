# Deploying On-Call Incident Rehearsal to Render (Free Static Site)

This repository contains the standalone **On-Call Incident Rehearsal** web application built with **React 19**, **Tailwind CSS v4**, and **Vite**. All scenario flows (incident alerting, investigation timer simulations, theories court, fix options, and decisions) run entirely client-side.

Deploying as a **Render Static Site** is the recommended hosting choice:
- **100% Free**: No charges and no credit card required.
- **Never Sleeps**: Unlike Render's free Web Services (which spin down after 15 minutes of inactivity), Static Sites are served directly from Render's global CDN and are **instantly available 24/7**.
- **Automatic HTTPS**: SSL certificates are provisioned automatically.
- **Zero Secrets**: Because the app runs client-side simulation logic, no API keys or backend environment secrets are required.

---

## 1. Prepare Git Repository

This folder is not yet connected to a remote Git repository. To deploy to Render, push this project to GitHub or GitLab:

```bash
cd "/Users/shivaprasad/Downloads/On-Call Incident Rehearsal"

# Initialize git repository
git init -b main

# Stage all files (AGENTS.md and CLAUDE.md have already been removed)
git add .

# Create initial commit
git commit -m "feat: initial commit for on-call incident rehearsal frontend"

# Create a new repository on GitHub (using GitHub CLI) or create one via github.com
gh repo create on-call-incident-rehearsal --public --source=. --push
```

*(If you don't use `gh` CLI, create an empty repository on [github.com](https://github.com/new), then run `git remote add origin <your-repo-url>` and `git push -u origin main`.)*

---

## 2. Deploy on Render

### Method A: Automatic Deployment using Blueprint (`render.yaml`)

1. Log in to [dashboard.render.com](https://dashboard.render.com/).
2. Click **New +** in the top navigation bar and select **Blueprint**.
3. Connect your GitHub/GitLab account and select your `on-call-incident-rehearsal` repository.
4. Render will detect `render.yaml` automatically:
   - **Service Type**: Static Site (`runtime: static`)
   - **Build Command**: `corepack enable && pnpm install --frozen-lockfile && pnpm run build`
   - **Publish Directory**: `./dist`
   - **Node Version**: `22`
   - **SPA Rewrite Rule**: `/*` → `/index.html`
5. Click **Apply**.
6. Render will build the site and provide your live URL (e.g. `https://on-call-incident-rehearsal.onrender.com`).

---

### Method B: Manual Dashboard Setup (Without Blueprint)

If you prefer setting it up manually without using `render.yaml`:

1. In the Render Dashboard, click **New +** → **Static Site**.
2. Connect your repository.
3. Configure the settings:
   - **Name**: `on-call-incident-rehearsal` (or your choice)
   - **Branch**: `main`
   - **Root Directory**: *(leave blank)*
   - **Build Command**: `corepack enable && pnpm install --frozen-lockfile && pnpm run build`
   - **Publish Directory**: `dist`
4. Expand **Advanced**:
   - Add Environment Variable:
     - Key: `NODE_VERSION`
     - Value: `22`
5. Click **Create Static Site**.
6. After the initial build finishes, go to **Redirects/Rewrites** in the left sidebar:
   - Click **Add Rule**
   - **Type**: `Rewrite`
   - **Source**: `/*`
   - **Destination**: `/index.html`
   - Click **Save Changes** *(this ensures client-side routes like `/alert` or `/profile` work on direct refresh)*.

---

## 3. Post-Deployment Verification Checklist

Once Render shows **"Live"**, open your assigned `.onrender.com` URL:

- [ ] **Initial Load**: The app loads immediately into the **Login** screen (`#login`).
- [ ] **Sign In**: Click **"Sign in as on-call engineer"** → navigates to the **Alert** screen (`#alert`).
- [ ] **Scenario Selection**: Click on the incident alert card (e.g., *Slow order queries & connection spikes*) → transitions to **Investigate** (`#investigate`).
- [ ] **Live Simulation**: Watch the 3-second investigation progress timer complete and auto-advance to **Theories** (`#theories`).
- [ ] **Theories & Fix**: Select the top-ranked theory (*Missing index on orders.customer_id*) → click **"Choose this diagnosis"** → inspect the **Fix** screen (`#fix`).
- [ ] **Safe Dry-Run & Decision**: Run the practice dry-run → click **"Proceed to decision"** (`#decision`) → approve or reject the remediation.
- [ ] **Profile & User Menu**: Click your avatar in the sidebar/header → navigate to **Profile** (`#profile`) and verify back navigation works.
- [ ] **Sign Out**: Click **Sign out** → returns cleanly to the **Login** screen.
- [ ] **Mobile Responsiveness**: Resize the browser down to mobile width (375px) → confirm bottom navigation and responsive layout adapt smoothly.

---

## 4. Teardown / Deletion

When you are finished testing and want to tear down the hosted app:

1. In the Render Dashboard, select the **on-call-incident-rehearsal** static site.
2. Click **Settings** in the left navigation menu.
3. Scroll down to the bottom **Danger Zone**.
4. Click **Delete Static Site** and type the service name to confirm.
5. The site and all deployed assets are immediately removed.
