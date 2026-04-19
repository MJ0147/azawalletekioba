# Use an official Python runtime as a parent image
FROM python:3.10-slim-trixie

# Set the working directory in the container
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
	openssl=3.5.5-1~deb13u2 libssl3t64=3.5.5-1~deb13u2 \
	&& rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Strip any Windows CRLF from startup script (safe no-op on LF files)
RUN sed -i 's/\r//' /app/start.sh && chmod +x /app/start.sh

# Primary entrypoint: inline sh -c so env-var expansion works on every
# platform without requiring an executable shell script on disk.
# Platforms (DigitalOcean, Cloud Run, etc.) that clear custom run commands
# will fall through to this CMD automatically.
CMD ["sh", "-c", "exec gunicorn -b 0.0.0.0:${PORT:-8080} -w ${GUNICORN_WORKERS:-4} -k uvicorn.workers.UvicornWorker --timeout ${GUNICORN_TIMEOUT:-120} --config /app/gunicorn.conf.py app.main:app"]