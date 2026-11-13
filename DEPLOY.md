# Cloud Run Deployment Guide

> **OnCall Rehearsal Agent** — Google Cloud Run deployment reference.
>
> SQLite is ephemeral on Cloud Run (see [Ephemeral Storage](#-ephemeral-storage) below).
> Do **not** put Firebase Hosting in front of this app — it strips all cookies
> except `__session`, which breaks sessions and CSRF.

---

## Prerequisites

| Tool | Minimum Version |
|------|----------------|
| `gcloud` CLI | Latest stable |
| Docker | 24+ |
| A GCP project with billing enabled | — |

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

---

## 1. Enable Required APIs

```bash
gcloud services enable run.googleapis.com
gcloud services enable secretmanager.googleapis.com
gcloud services enable artifactregistry.googleapis.com
```

---

## 2. Create Secrets in Secret Manager

> **Never bake secrets into the Docker image or commit them to git.**
> Every secret below must be stored in Secret Manager and mounted at runtime.

```bash
# Anthropic API key
echo -n "sk-ant-YOUR_KEY" | gcloud secrets create ANTHROPIC_API_KEY --data-file=-

# Session signing secret (minimum 32 chars — generate with openssl)
openssl rand -base64 32 | tr -d '\n' | gcloud secrets create SECRET_KEY --data-file=-

# Initial admin credentials (see Ephemeral Storage section)
echo -n "admin" | gcloud secrets create ADMIN_USERNAME --data-file=-
openssl rand -base64 18 | tr -d '\n' | gcloud secrets create ADMIN_PASSWORD --data-file=-
```

> **Rotate `ADMIN_PASSWORD` immediately** after first login. The admin account
> resets on every new container instance (see below).

---

## 3. Create Artifact Registry and Push Image

```bash
gcloud artifacts repositories create oncall-repo \
  --repository-format=docker \
  --location=us-central1 \
  --description="OnCall Rehearsal Agent images"

gcloud auth configure-docker us-central1-docker.pkg.dev

docker build -t us-central1-docker.pkg.dev/YOUR_PROJECT_ID/oncall-repo/oncall-agent:latest .

docker push us-central1-docker.pkg.dev/YOUR_PROJECT_ID/oncall-repo/oncall-agent:latest
```

---

## 4. Deploy to Cloud Run

```bash
gcloud run deploy oncall-agent \
  --image us-central1-docker.pkg.dev/YOUR_PROJECT_ID/oncall-repo/oncall-agent:latest \
  --region us-central1 \
  --platform managed \
  --max-instances 1 \
  --min-instances 0 \
  --memory 512Mi \
  --cpu 1 \
  --port 8080 \
  --no-allow-unauthenticated \
  --set-secrets="ANTHROPIC_API_KEY=ANTHROPIC_API_KEY:latest,SECRET_KEY=SECRET_KEY:latest,ADMIN_USERNAME=ADMIN_USERNAME:latest,ADMIN_PASSWORD=ADMIN_PASSWORD:latest" \
  --set-env-vars="PRODUCTION=true,AGENT_MODE=live,CLAUDE_MODEL=claude-sonnet-5-5,CORS_ORIGIN=https://YOUR_SERVICE_URL.run.app"
```

> `--max-instances 1` keeps costs and concurrency predictable for a demo/training tool.
> Raise only if you need concurrent users.

---

## 5. Grant Secret Manager Access to the Cloud Run Service Account

```bash
# Get the Cloud Run service account email
PROJECT_NUMBER=$(gcloud projects describe YOUR_PROJECT_ID --format='value(projectNumber)')
SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

# Grant access to each secret
for SECRET in ANTHROPIC_API_KEY SECRET_KEY ADMIN_USERNAME ADMIN_PASSWORD; do
  gcloud secrets add-iam-policy-binding $SECRET \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/secretmanager.secretAccessor"
done
```

---

## 6. Post-Deploy Health Check

```bash
SERVICE_URL=$(gcloud run services describe oncall-agent --region us-central1 --format='value(status.url)')

curl "$SERVICE_URL/health"
# Expected: {"status": "ok"}
```

---

## 7. Updating the Image

```bash
docker build -t us-central1-docker.pkg.dev/YOUR_PROJECT_ID/oncall-repo/oncall-agent:latest .

docker push us-central1-docker.pkg.dev/YOUR_PROJECT_ID/oncall-repo/oncall-agent:latest

gcloud run services update-traffic oncall-agent --to-latest --region us-central1
```

---

## ⚠ Ephemeral Storage

Cloud Run containers are **stateless and ephemeral**. Every new container instance starts
with a fresh filesystem — including the SQLite database.

| What resets on redeploy / scale-out | Impact |
|--------------------------------------|--------|
| `oncall.db` (users, sessions, audit log) | All users and sessions are lost |
| Admin account | Must be re-created automatically |

### How admin re-creation works

At startup, `app/main.py` calls `_seed_admin_from_env()`. If `ADMIN_USERNAME` and
`ADMIN_PASSWORD` are present (injected via Secret Manager), it creates or updates
the admin user before accepting traffic.

**You do not need to do anything after a redeploy** — the admin account is
automatically recreated on each container start.

> Log line to look for: `Admin user 'admin' created from ADMIN_USERNAME/ADMIN_PASSWORD env vars.`

### What this means for a production audience

If you need durable users and an audit trail across deploys, you must migrate to
a managed database (Cloud SQL PostgreSQL). The database layer is in `app/database.py`
and uses standard parameterised SQL — no ORM. Swapping the driver is a contained
change, but it is **out of scope** for this release. The team must sign off before
any database layer rewrite.

---

## Security Notes

| Item | Status |
|------|--------|
| Container runs as non-root (`appuser`, UID 1001) | ✅ Dockerfile |
| No secrets baked into image | ✅ All via Secret Manager |
| `answer_key.txt` files chmod 640, never served over HTTP | ✅ Dockerfile + app routing |
| `.env` excluded from image | ✅ `.dockerignore` |
| `.git` and `tests/` excluded from image | ✅ `.dockerignore` |
| `PRODUCTION=true` enforces HTTPS-only cookies + HSTS | ✅ Set in deploy command |
| `--no-allow-unauthenticated` requires IAM or VPC | ✅ Deploy flag |
| Do NOT use Firebase Hosting in front | ✅ Documented here |

> Firebase Hosting strips all cookies except `__session`. This would silently
> break session authentication and CSRF validation. If a CDN layer is ever needed,
> use Cloud CDN on a Cloud Load Balancer instead, and confirm cookie pass-through
> is configured before enabling it.
