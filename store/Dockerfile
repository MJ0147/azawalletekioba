FROM python:3.11-slim-trixie

ENV PYTHONUNBUFFERED=1
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
	openssl=3.5.5-1~deb13u2 libssl3t64=3.5.5-1~deb13u2 \
	&& rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Cloud Run sets the PORT environment variable automatically
# Using gunicorn for production as specified in best practices
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 store_service.wsgi:application