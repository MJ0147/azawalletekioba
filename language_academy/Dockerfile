FROM python:3.11-slim-bookworm
ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Apply OS security patches
RUN apt-get update && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

RUN groupadd --system appgroup \
    && useradd --system --gid appgroup --no-create-home appuser \
    && chown -R appuser:appgroup /app

USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request, os; urllib.request.urlopen('http://localhost:' + os.environ.get('PORT','8080') + '/')" 2>/dev/null || exit 1

CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 language_academy.wsgi:application