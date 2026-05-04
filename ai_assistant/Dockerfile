# Use an official Python runtime as a parent image
FROM python:3.10-slim-bookworm

# Set the working directory in the container
WORKDIR /app

# Apply OS security patches
RUN apt-get update && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Strip any Windows CRLF from startup script (safe no-op on LF files)
RUN sed -i 's/\r//' /app/start.sh && chmod +x /app/start.sh

RUN groupadd --system appgroup \
    && useradd --system --gid appgroup --no-create-home appuser \
    && chown -R appuser:appgroup /app

USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request, os; urllib.request.urlopen('http://localhost:' + os.environ.get('PORT','8080') + '/health')" 2>/dev/null || exit 1

# Primary entrypoint: inline sh -c so env-var expansion works on every
# platform without requiring an executable shell script on disk.
# Platforms (DigitalOcean, Cloud Run, etc.) that clear custom run commands
# will fall through to this CMD automatically.
CMD ["sh", "-c", "exec gunicorn -b 0.0.0.0:${PORT:-8080} -w ${GUNICORN_WORKERS:-4} -k uvicorn.workers.UvicornWorker --timeout ${GUNICORN_TIMEOUT:-120} --config /app/gunicorn.conf.py app.main:app"]