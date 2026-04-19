EKIOBA Deployment

Local Orchestration (Docker Compose)

Run all local services:

docker compose up --build

Services:

store on http://localhost:8001

cargo on http://localhost:8002

hotels on http://localhost:8003

language_academy on http://localhost:8004

ai_assistant on http://localhost:8005

frontend on http://localhost:3000

Local Frontend Development (Standalone)

To run only the frontend locally (useful for UI testing) while pointing to local backend services:

./run_frontend_local.ps1

CI/CD (GitHub Actions)

Current workflows:

.github/workflows/ci.yml: integration build and test on develop

.github/workflows/django.yml: Django checks on main

.github/workflows/cloud-run.yml: deploy universal service to Google Cloud Run

Google Cloud Run

The deployment is now consolidated into a single "Universal" container ekioba-universal. This container runs Nginx, which routes traffic to the Frontend, Store, Cargo, Hotels, and AI Assistant services running internally.

Google Secret Manager (Blockchain Keys)

Create required secrets:

echo -n "https://api.mainnet-beta.solana.com" | gcloud secrets create SOLANA_RPC_URL --data-file=-
echo -n "<your-ton-api-key>" | gcloud secrets create TON_API_KEY --data-file=-
echo -n "<your-django-secret-key>" | gcloud secrets create DJANGO_SECRET_KEY --data-file=-
echo -n "postgresql://<user>:<password>@<digitalocean-host>:26257/ekioba_store?sslmode=require" | doctl secrets create COCKROACHDB_STORE_URL --data-file=-
echo -n "postgresql://<user>:<password>@<digitalocean-host>:26257/ekioba_hotels?sslmode=require" | doctl secrets create COCKROACHDB_HOTELS_URL --data-file=-

Grant Cloud Run runtime service account access:

gcloud secrets add-iam-policy-binding SOLANA_RPC_URL \
  --member="serviceAccount:<runtime-service-account>" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding TON_API_KEY \
  --member="serviceAccount:<runtime-service-account>" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding DJANGO_SECRET_KEY \
  --member="serviceAccount:<runtime-service-account>" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding COCKROACHDB_STORE_URL \
  --member="serviceAccount:<runtime-service-account>" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding COCKROACHDB_HOTELS_URL \
  --member="serviceAccount:<runtime-service-account>" \
  --role="roles/secretmanager.secretAccessor"

Required GitHub Repository Secrets

Set these in GitHub Actions secrets:

GCP_PROJECT_ID

GCP_REGION (example: us-central1)

GCP_WORKLOAD_IDENTITY_PROVIDER

GCP_SERVICE_ACCOUNT

Optional app secrets still used by tests/workflows:

DJANGO_SECRET_KEY

TON_API_KEY

SOLANA_API_KEY

Environment File Safety

Never commit real .env files to source control.

Keep only template files like .env.example in git.

For production deployments, inject secrets only from Google Secret Manager and/or CI secret stores.

Do not bake secrets into Docker images, compose files, or committed config.

Pre-deployment check:

git ls-files ".env*" "**/.env*"

The command should return no real .env files.

Blockchain Integration

Solana

Frontend wallet connection: @solana/wallet-adapter-react + @solana/wallet-adapter-react-ui

Checkout wallet: Phantom (@solana/wallet-adapter-wallets)

Chain SDK: @solana/web3.js (and optional @solana/pay for QR/request links)

Backend verification: keep signature verification in store/core/payments.py using getTransaction

TON

Frontend wallet connection: Tonkeeper via @tonconnect/sdk (or @tonconnect/ui-react)

Chain SDK: TON Connect SDK for wallet/session and signed transfers

Backend verification: validate tx_hash against TON API as implemented in store/core/payments.py

Smart Contracts And Tokens

Solana: SPL token mint for vouchers/loyalty points

TON: Jetton mint for vouchers/loyalty points

Cross-service usage model:

store: apply discount tokens at checkout

cargo: redeem tokens for delivery fee discounts

hotels: redeem tokens for booking incentives

language_academy: issue tokens for quiz/streak achievements

Recommended Secret Manager Entries

SOLANA_RPC_URL

TON_API_KEY

TON_CONNECT_MANIFEST_URL (if using hosted TonConnect manifest)

SPL_TOKEN_MINT_ADDRESS

TON_JETTON_MASTER_ADDRESS