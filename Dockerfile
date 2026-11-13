# ── Stage 1: Build React frontend ─────────────────────────────────────────
FROM node:24-slim AS frontend-builder

WORKDIR /build/frontend

# Install pnpm via corepack (bundled with Node 24)
RUN corepack enable

# Copy only package manifests first for layer caching
COPY frontend/package.json frontend/pnpm-lock.yaml ./

RUN pnpm install --frozen-lockfile

# Copy source and build
COPY frontend/ ./
RUN pnpm build
# dist/ is now at /build/frontend/dist


# ── Stage 2: Python runtime ────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Never run as root in the container
RUN groupadd --gid 1001 appgroup \
 && useradd --uid 1001 --gid appgroup --no-create-home --shell /bin/false appuser

WORKDIR /app

# Install Python deps as root (into /usr/local) before dropping privileges.
# Copy requirements first for layer caching.
COPY requirements.txt ./
# Install only prod deps — pip-audit / pytest are dev-only but are in
# requirements.txt for auditability; they add no attack surface at runtime.
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY app/        ./app/
COPY data/       ./data/
COPY static/     ./static/
COPY scripts/    ./scripts/
COPY create_admin.py ./

# Copy built frontend assets from Stage 1
COPY --from=frontend-builder /build/frontend/dist ./frontend/dist

# Restrict data directory: answer_key files must not be served over HTTP.
# They are protected at the app layer (never mounted as static), but we also
# tighten OS permissions so a misconfigured static mount cannot expose them.
RUN find /app/data -name "answer_key.txt" -exec chmod 640 {} \;

# Hand ownership of /app to appuser (data files are read-only for the process)
RUN chown -R appuser:appgroup /app

# Drop to non-root for all subsequent layers and runtime
USER appuser

# Expose the port Cloud Run will route to
EXPOSE 8080

# Health check: Cloud Run polls /health; fail fast on startup problems
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')"

# Entrypoint: use exec form so SIGTERM reaches uvicorn directly
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
