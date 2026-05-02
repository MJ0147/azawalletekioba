EKIOBA Deployment

Supported deployment path

Local Docker build and Docker Hub push scripts have been removed from the repository. The supported deployment path is GitHub Actions.

GitHub Actions workflows

.github/workflows/ci.yml: runs backend and frontend validation checks

.github/workflows/azure-pipeline.yml: single deployment pipeline that targets Azure Web Apps

.github/workflows/django.yml: runs Django validation on main

Azure deployment secrets and variables

Required secrets:

AZURE_CREDENTIALS

AZURE_BACKEND_APP

AZURE_FRONTEND_APP

BACKEND_URL_PROD

Optional for tests/validation:

DATABASE_URL (secret or repository variable)

DJANGO_SECRET_KEY

TON_API_KEY

SOLANA_API_KEY

Recommended usage

1. Push changes to a feature branch and open a pull request.
2. Let GitHub Actions validate the branch.
3. Merge to main to trigger the deployment workflow for the target platform.
4. Use workflow_dispatch when you need a manual deployment run.

Repository secrets

Keep deployment credentials in GitHub Actions secrets or repository variables only. Do not rely on local Docker login state or local image publishing.

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