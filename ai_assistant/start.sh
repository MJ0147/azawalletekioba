#!/bin/sh
set -e

PORT_VALUE="${PORT:-8080}"

exec gunicorn \
  -b "0.0.0.0:${PORT_VALUE}" \
  -w "${GUNICORN_WORKERS:-4}" \
  -k uvicorn.workers.UvicornWorker \
  --timeout "${GUNICORN_TIMEOUT:-120}" \
  app.main:app
