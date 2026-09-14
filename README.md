# EKIOBA

EKIOBA is a multi-service workspace containing the storefront, cargo, hotels, language academy, AI assistant, and frontend applications.

## Platform

Supabase is the only platform EKIOBA depends on: Postgres for every service's data, Row Level Security for access control, and Edge Functions as the hosting target. The Python services are being ported to Edge Functions; see `DEPLOYMENT.md` for the limits that shape that work.

Primary workflows:

- `.github/workflows/ci.yml` validates backend and frontend on pull requests and pushes.

## Working locally

Run the services with `docker compose up`, or with their native runtimes. Point `DATABASE_URL` at your Supabase Postgres connection string, or leave it unset to use SQLite.

See `DEPLOYMENT.md` for Supabase connection details and required secrets.
