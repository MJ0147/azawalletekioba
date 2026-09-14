#!/bin/bash
set -e

echo "==> Running database migrations..."
python manage.py migrate --no-input

echo "==> Collecting static files..."
python manage.py collectstatic --no-input --clear 2>/dev/null || true

echo "==> Creating/updating the backend admin account..."
# Reads ADMIN_EMAIL / ADMIN_PASSWORD (falling back to DJANGO_SUPERUSER_*).
# Idempotent, and re-syncs the password so a rotated credential takes effect.
# A missing password is not fatal here - the app should still start.
python manage.py createadmin || echo "    (skipped: no admin credentials configured)"

echo "==> Starting gunicorn..."
exec gunicorn store_service.wsgi:application \
    --bind "0.0.0.0:${PORT:-8000}" \
    --workers 2 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
