# EKIOBA Deployment Guide

## Platform: Supabase

Azure has been removed. Supabase is the only platform EKIOBA depends on.

| Component | Supabase feature |
|-----------|------------------|
| Database | Supabase Postgres — `DATABASE_URL` for store, hotels and ai_assistant; `SUPABASE_URL` + keys for the frontend |
| Schema | SQL files in `Knowledge Base/Supabase/`, run in the SQL Editor |
| Access control | Row Level Security on every table; the service-role key is used server-side only |
| Secrets | Edge Function secrets (`supabase secrets set`) and GitHub Actions secrets |
| Hosting | Supabase Edge Functions — migration in progress, see below |

### Limits that shape the migration

- **Edge Functions run TypeScript on Deno, not Python.** The FastAPI and Django services have to be
  ported before they can be hosted on Supabase.
- **No HTML on the default domain.** Responses with `text/html` from `*.supabase.co` are rewritten
  to `text/plain`. Serving pages needs a Pro plan plus the custom-domain add-on.
- **2 s CPU time and 256 MB memory per request.** Long-running work must stay off Edge Functions.

Until the port is complete, run the services locally with `docker compose up`.

---

## Connecting to Supabase Postgres

1. Supabase dashboard → **Connect** → copy the **Session pooler** connection string.
2. Keep `sslmode=require` — Supabase only accepts TLS.
3. URL-encode any special characters in the database password.
4. Set it as `DATABASE_URL` (or `STORE_DATABASE_URL` / `HOTELS_DATABASE_URL` for docker compose).

Leaving `DATABASE_URL` unset (or pointing it at `sqlite:///…`) uses SQLite, which is what the
test suites do.

---

## GitHub Actions Workflows

| File | Purpose |
|------|---------|
| `.github/workflows/ci.yml` | PR validation (backend + frontend, no deploy) |
| `.github/workflows/django.yml` | Django tests |
| `.github/workflows/no-mock-local-tests.yml` | Django tests with in-memory SQLite |

---

## Environment File Safety

- Never commit real `.env` files to source control.
- Keep only `.env.example` in git.
- For production, inject secrets from **Supabase** and GitHub Actions secrets only.
- Do not bake secrets into Docker images or compose files.

Pre-deployment check:
```sh
git ls-files ".env*" "**/.env*"
```
Should return no real `.env` files.

---

Blockchain Integration

TON is the only chain EKIOBA settles on.

Frontend wallet connection: TON Connect UI (`@tonconnect/ui`, pinned to 2.4.4), loaded from a CDN
in `frontend/templates/base.html`. The UMD bundle publishes itself as `window.TON_CONNECT_UI`.

TON Connect manifest: served dynamically at `GET /tonconnect-manifest.json`. Its `url` is derived
from the incoming request (or `PUBLIC_BASE_URL`) because wallets reject a manifest whose `url` does
not match the origin requesting the connection. The icon must be a real PNG.

Payment payloads: `frontend/services/ton.py` resolves the sender's Jetton wallet via the TON API
`get_wallet_address` get-method and builds a TL-B `transfer#0f8a7ea5` body (base64 BOC) for
`tonConnectUI.sendTransaction`.

Backend verification: validate tx_hash against the TON API as implemented in store/core/payments.py

Pricing: `frontend/services/dedust.py` reads live IDIA pricing from DeDust liquidity pools.
DeDust's REST API only exposes the full pool set (`GET /v2/pools`, ~5 MB, ~60 s) with no
single-pool endpoint, so the service reads the pools on-chain instead: the DeDust Factory derives
the pool address deterministically via `get_pool_address`, then the pool's `get_reserves` gives
live reserves. IDIA is priced IDIA -> TON (TON/IDIA pool) -> USD (TON/USDT pool) -> NGN.

`GET /api/pay/idia-rate` reports `source` ("dedust" | "coingecko" | "fallback") and `live`.
`GET /api/pay/dedust-market` returns pool diagnostics. As of this writing there is no TON/IDIA
pool on DeDust, so pricing falls back to IDIA_NGN_RATE and `live` is false; once a pool is
created the live price flows through with no code change.

FX (USDT -> NGN): `frontend/services/flutterwave.py` supplies the naira leg from Flutterwave's
`GET /v3/transfers/rates` (needs FLW_SECRET_KEY). Flutterwave quotes fiat only, so USD is used as
the USDT proxy. The rate is cached 5 minutes and rejected if it falls outside FLW_RATE_MIN..MAX,
which catches an inverted or wrong-currency quote before it can misprice a basket. Falls back to
CoinGecko tether->NGN, then the static USDT_NGN_RATE. `GET /api/pay/fx` returns FX diagnostics and
`/api/pay/idia-rate` reports `fx_source` / `fx_live`.

Note the two legs are independent: IDIA can be unpriced (`live: false`) while FX is live
(`fx_live: true`), in which case the IDIA_USD_RATE placeholder is converted at the live rate —
unless IDIA_NGN_RATE is explicitly pinned, which overrides everything.

Smart Contracts And Tokens

IDIA Jetton master (mainnet): EQC8QIjU-uXwrlj9B9Zc0ZBIaTS5TLzFb6djJIRwyLa6Enqs — 9 decimals

DeDust Factory (mainnet): EQBfBWT7X2BHg9tXAxzhz2aKiNTU1tpt5NsiK0uSDW_YAJ67

Cross-service usage model:

store: apply discount tokens at checkout

cargo: redeem tokens for delivery fee discounts

hotels: redeem tokens for booking incentives

language_academy: issue tokens for quiz/streak achievements

Recommended Secret Manager Entries

TON_API_KEY

TON_MERCHANT_WALLET

IDIA_TON_JETTON_ADDRESS

PUBLIC_BASE_URL (only when the public origin cannot be derived from the request)

TON_JETTON_MASTER_ADDRESS
