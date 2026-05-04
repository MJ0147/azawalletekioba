# EKIOBA Deployment Guide

## Deployment Target: Azure Only

All deployment targets (GCP Cloud Run, DigitalOcean App Platform, AWS) have been removed.
The sole deployment stack is **Azure**.

---

## Azure Infrastructure

| Component | Resource |
|-----------|----------|
| Container Registry | `azawallet.azurecr.io` |
| Backend Web App | `$AZURE_BACKEND_APP` (language_academy) |
| Frontend Web App | `$AZURE_FRONTEND_APP` (frontend) |
| Kubernetes | AKS — namespace `ekioba` |
| Database | Azure SQL Managed Instance (port 3342) |
| Secrets | Azure Key Vault (verify with `verify_azure_secrets.ps1`) |

---

## GitHub Actions Workflows

| File | Purpose |
|------|---------|
| `.github/workflows/azure-pipeline.yml` | Primary CI/CD — Trivy scan → validate → deploy Web Apps + AKS |
| `.github/workflows/ci.yml` | PR validation (backend + frontend, no deploy) |
| `.github/workflows/no-mock-local-tests.yml` | Django tests with in-memory SQLite |

## Azure DevOps Pipeline

`azure-pipelines.yml` — Builds root `Dockerfile` → pushes to `azawallet.azurecr.io` with `$(Build.BuildId)` tag.

---

## Required GitHub Secrets

```
AZURE_CREDENTIALS          # Service principal JSON
AZURE_BACKEND_APP          # Azure Web App name (language_academy)
AZURE_FRONTEND_APP         # Azure Web App name (frontend)
AKS_RESOURCE_GROUP         # Resource group containing the AKS cluster
AKS_CLUSTER_NAME           # AKS cluster name
```

## Repository Variable

```
ENABLE_AZURE_DEPLOY=true   # Set to enable deploy jobs on push to main
```

---

## Deploy Flow

1. Push to a feature branch → opens PR → `ci.yml` validates (no deploy).
2. Merge to `main` → `azure-pipeline.yml` triggers:
   - **scan-images**: Trivy CRITICAL/HIGH scan gates deploy.
   - **validate-backend**: Django tests (SQLite in-memory).
   - **validate-frontend**: Python import check.
   - **deploy-backend** + **deploy-frontend**: Azure Web Apps via `azure/webapps-deploy@v3`.
   - **deploy-k8s**: AKS manifest apply with git SHA image tag substitution.
3. Use `workflow_dispatch` for manual deploys.

---

## Azure Credential Rotation

If Azure login fails with `AADSTS7000222`, the service principal secret is expired.

1. Rotate secret: `az ad sp credential reset --id <SP_APP_ID>`
2. Update GitHub secret `AZURE_CREDENTIALS` with the new JSON payload.
3. While rotating, set `ENABLE_AZURE_DEPLOY` to `false` so validation jobs still run.

---

## Key Vault Secret Verification

```powershell
.\verify_azure_secrets.ps1 -KeyVaultName "ekioba-kv"
```

---

## Environment File Safety

- Never commit real `.env` files to source control.
- Keep only `.env.example` in git.
- For production, inject secrets from **Azure Key Vault** and GitHub Actions secrets only.
- Do not bake secrets into Docker images or compose files.

Pre-deployment check:
```sh
git ls-files ".env*" "**/.env*"
```
Should return no real `.env` files.

Blockchain Integration

Solana

Frontend wallet connection: @solana/wallet-adapter-react + @solana/wallet-adapter-react-ui

Checkout wallet: Phantom + Solflare (@solana/wallet-adapter-phantom, @solana/wallet-adapter-solflare)

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