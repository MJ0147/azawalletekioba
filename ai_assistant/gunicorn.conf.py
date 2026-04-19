"""
Gunicorn configuration for Iyobo AI Assistant.
Values here are defaults only; environment variables passed to the container
at runtime (PORT, GUNICORN_WORKERS, GUNICORN_TIMEOUT) take precedence because
start.sh and the Dockerfile CMD both pass them explicitly on the command line.
"""

import multiprocessing
import os

# Networking
bind = f"0.0.0.0:{os.environ.get('PORT', '8080')}"

# Workers — default to (2 x CPUs) + 1, capped at the env override if set
workers = int(os.environ.get("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))

# Worker class — must match the -k flag passed on the CLI
worker_class = "uvicorn.workers.UvicornWorker"

# Timeout — long enough for cold-start DB connections
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "120"))

# Logging — write to stdout so Cloud Run / DO Logs capture it
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("LOG_LEVEL", "info")
