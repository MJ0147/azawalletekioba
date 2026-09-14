# EKIOBA Security Architecture

## Recommended Security Structure

```text
[ Next.js Frontend ] --> HTTPS --> [ Django/FastAPI Backend ] --> Local I/O --> [ SQLite ]
         |                                |                                    |
   Auth via JWT/OAuth2              Secrets via GCP SM                  File Permissions
```

## Control Layers

### 1. Frontend to Backend (HTTPS)
- Enforce HTTPS only for all public endpoints.
- Use JWT/OAuth2 access tokens in `Authorization: Bearer <token>`.
- Store access tokens in secure HTTP-only cookies when possible.
- Configure CORS allowlists to only trusted frontend origins.

### 2. Backend Authentication and Authorization
- Use OAuth2/OIDC provider (Google, Auth0, Firebase Auth, or equivalent).
- Validate JWT signature, issuer (`iss`), audience (`aud`), and expiry (`exp`) on every protected request.
- Apply route-level authorization by role/permission claims.
- Keep payment endpoints idempotent and log signed transaction references only.

### 3. Secrets Management (GCP Secret Manager)
- Keep keys/tokens out of code and `.env` in production.
- Store blockchain and app secrets in Secret Manager:
  - `TON_API_KEY`
  - `TON_MERCHANT_WALLET`
  - `DJANGO_SECRET_KEY`
  - `SQLITE_DB_PATH`
  - `TELEGRAM_BOT_TOKEN`
- Grant least-privilege access via `roles/secretmanager.secretAccessor` to runtime service accounts only.
  - Ensure the database file resides in a persistent volume if using ephemeral containers (e.g., Cloud Run with GCS fuse).

### 4. Backend to Database (Local I/O)
- Ensure the database file is stored in a directory with restricted read/write permissions.
- For high-concurrency environments, enable WAL (Write-Ahead Logging) mode.
- Regularly back up the `.db` file to secure object storage (e.g., Google Cloud Storage).

### 5. Database Security (File Permissions)
- Restrict access to the database file to the service runtime user only (e.g., `chmod 600`).
- Use SQLite's `STRICT` mode in table definitions to enforce data integrity.
- Consider using SQLCipher if at-rest encryption is required beyond filesystem-level encryption.

## Service Hardening Checklist

- [ ] HTTPS enabled at ingress/load balancer.
- [ ] JWT/OAuth2 validation middleware enabled for protected endpoints.
- [ ] CORS restricted to approved frontend domains.
- [ ] Secrets loaded from GCP Secret Manager in Cloud Run.
- [ ] SQLite database file permissions hardened.
- [ ] CI/CD does not print secrets in logs.
- [ ] Security headers enabled (HSTS, X-Content-Type-Options, X-Frame-Options, CSP).

## EKIOBA Implementation Notes

- Move from `COCKROACHDB_URL` (or `MYSQL_URL`) to `SQLITE_DB_PATH` in environment configurations.
- Local development uses a local file; production deployments should mount a persistent disk to maintain data across container restarts.
- For Iyobo and blockchain endpoints, apply token-based auth before enabling public write actions.
