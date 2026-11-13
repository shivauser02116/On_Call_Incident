# ── Python runtime ────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Never run as root in the container
RUN groupadd --gid 1001 appgroup \
 && useradd --uid 1001 --gid appgroup --no-create-home --shell /bin/false appuser

WORKDIR /app

# Install Python deps as root (into /usr/local) before dropping privileges.
# Copy requirements first for layer caching.
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY app/        ./app/
COPY data/       ./data/
COPY static/     ./static/
COPY scripts/    ./scripts/
COPY create_admin.py ./

# Copy prebuilt frontend assets (already compiled in repository)
COPY frontend/dist/ ./frontend/dist/

# Restrict data directory: answer_key files must not be served over HTTP.
RUN find /app/data -name "answer_key.txt" -exec chmod 640 {} \;

# Hand ownership of /app to appuser (data files are read-only for the process)
RUN chown -R appuser:appgroup /app

# Drop to non-root for all subsequent layers and runtime
USER appuser

# Expose the port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')"

# Entrypoint: use exec form so SIGTERM reaches uvicorn directly
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
