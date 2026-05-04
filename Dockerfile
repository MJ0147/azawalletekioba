# Root Dockerfile — builds the language_academy (Django) service for Azure DevOps / ACR.
# Azure DevOps azure-pipelines.yml references this file directly.
FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

WORKDIR /app

# Apply OS security patches + install curl for HEALTHCHECK
RUN apt-get update && apt-get upgrade -y --no-install-recommends \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY language_academy/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY language_academy/ .

RUN groupadd --system appgroup \
    && useradd --system --gid appgroup --no-create-home appuser \
    && chown -R appuser:appgroup /app

USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8080}/ || exit 1

CMD exec gunicorn --bind :${PORT:-8080} --workers 2 --threads 4 --timeout 60 language_academy.wsgi:application
