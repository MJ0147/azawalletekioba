from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, Form, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from agent import get_dashboard_forecast

BASE_DIR = Path(__file__).resolve().parent
PUBLIC_DIR = BASE_DIR / "public"

app = FastAPI(title="Ekioba Frontend")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

STORE_BACKEND_URL = os.getenv("STORE_BACKEND_URL", "http://localhost:8001/api/products/")
STORE_PAYMENTS_URL = os.getenv("STORE_PAYMENTS_URL", "http://localhost:8001/payments/process/")
AI_ASSISTANT_URL = os.getenv("AI_ASSISTANT_URL", "http://localhost:8005")
FRONTEND_IYOBO_URL = os.getenv("FRONTEND_IYOBO_URL", "/chat")
SOLANA_MERCHANT_WALLET = os.getenv("SOLANA_MERCHANT_WALLET", "")
TON_MERCHANT_WALLET = os.getenv("TON_MERCHANT_WALLET", "")

FALLBACK_PRODUCTS: list[dict[str, Any]] = [
    {
        "id": "1",
        "name": "Bronze Head of Oba Ozolua",
        "description": "Miniature replica of a classic Edo bronze casting.",
        "price": 25000,
        "category": "jewelry",
        "image": "https://olive-adorable-cephalopod-171.mypinata.cloud/ipfs/bafkreiahf52abfi6nzgnkhw5i2gcvxap4aszgk254lqt4qx6wzgnewwrhy",
    },
    {
        "id": "2",
        "name": "Ivory Mask Pendant",
        "description": "Inspired by the Queen Mother Idia mask.",
        "price": 28000,
        "category": "jewelry",
        "image": "https://olive-adorable-cephalopod-171.mypinata.cloud/ipfs/bafkreibsg5ra3vkzf4o42xiyqncvopam5cmueeaa7n3fmxy7jncetnvozu",
    },
    {
        "id": "3",
        "name": "Royal Vintage of Oba Ovonramen",
        "description": "Traditional royal vintage attire.",
        "price": 99000,
        "category": "fashion",
        "image": "https://olive-adorable-cephalopod-171.mypinata.cloud/ipfs/bafkreiclb35ofqhxaizqvmjbktdugdvxxkymlrrypqtc4o7rvkh5serxm4",
    },
    {
        "id": "4",
        "name": "Coral Bead",
        "description": "Coral beads representing status and ceremony.",
        "price": 10000,
        "category": "fashion",
        "image": "https://olive-adorable-cephalopod-171.mypinata.cloud/ipfs/bafkreih5dzvbn7rdt3lonovlnyq5kxzlr76ji4citkyrfdqfwjpgk46qsy",
    },
    {
        "id": "5",
        "name": "Benin Bronze Plaque (Leopard)",
        "description": "Commemorative plaque with royal leopard motif.",
        "price": 45000,
        "category": "art",
        "image": "https://olive-adorable-cephalopod-171.mypinata.cloud/ipfs/bafkreiahf52abfi6nzgnkhw5i2gcvxap4aszgk254lqt4qx6wzgnewwrhy",
    },
    {
        "id": "6",
        "name": "Palm Oil",
        "description": "Undiluted palm oil from Okomu farms.",
        "price": 30000,
        "category": "food",
        "image": "https://olive-adorable-cephalopod-171.mypinata.cloud/ipfs/bafybeicqkclmtsxhzsazrqd4qtr3byuxpeshgwasknsfnzqrnys6xbo3uq/",
    },
]

async def load_products() -> tuple[list[dict[str, Any]], bool]:
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(STORE_BACKEND_URL, headers={"Accept": "application/json"})
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, list) and payload:
                return payload, False
    except Exception:
        pass

    return FALLBACK_PRODUCTS, True


def category_distribution(products: list[dict[str, Any]]) -> dict[str, int]:
    buckets: dict[str, int] = {}
    for product in products:
        key = str(product.get("category") or "other")
        buckets[key] = buckets.get(key, 0) + 1
    return buckets


@app.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    products, using_fallback = await load_products()
    chart_data = category_distribution(products)
    forecast = await get_dashboard_forecast()
    context = {
        "request": request,
        "forecast": forecast,
        "products": products,
        "using_fallback": using_fallback,
        "products_json": json.dumps(products),
        "chart_labels": list(chart_data.keys()),
        "chart_values": list(chart_data.values()),
        "iyobo_url": FRONTEND_IYOBO_URL,
        "ton_wallet": TON_MERCHANT_WALLET,
        "solana_wallet": SOLANA_MERCHANT_WALLET,
    }
    return templates.TemplateResponse("index.html", context)


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    forecast = await get_dashboard_forecast()
    return templates.TemplateResponse("dashboard.html", {"request": request, "forecast": forecast})


@app.get("/wallet-dashboard", response_class=HTMLResponse)
async def wallet_dashboard_html(request: Request) -> HTMLResponse:
    """HTML page for wallet dashboard with forecast charts and predictions."""
    forecast = await get_dashboard_forecast()
    return templates.TemplateResponse("wallet_dashboard.html", {
        "request": request,
        "forecast": forecast,
        "wallet": {
            "solana_wallet": SOLANA_MERCHANT_WALLET or "Not configured",
            "ton_wallet": TON_MERCHANT_WALLET or "Not configured",
        }
    })


async def _dashboard_payload() -> JSONResponse:
    return JSONResponse(await get_dashboard_forecast())


@app.get("/api/dashboard")
async def dashboard_data() -> JSONResponse:
    return await _dashboard_payload()


@app.get("/api/dashboard/forecast")
async def dashboard_forecast() -> JSONResponse:
    return await _dashboard_payload()


@app.get("/api/wallet/dashboard")
async def wallet_dashboard() -> JSONResponse:
    """Wallet dashboard endpoint with forecast data and predictions."""
    forecast = await get_dashboard_forecast()
    return JSONResponse({
        "wallet": {
            "chains": ["solana", "ton"],
            "solana_wallet": SOLANA_MERCHANT_WALLET,
            "ton_wallet": TON_MERCHANT_WALLET,
        },
        "forecast": forecast,
        "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
    })


@app.get("/partials/products", response_class=HTMLResponse)
async def products_partial(request: Request) -> HTMLResponse:
    products, using_fallback = await load_products()
    return templates.TemplateResponse(
        "partials/products_grid.html",
        {"request": request, "products": products, "using_fallback": using_fallback},
    )


@app.get("/api/store/products")
async def store_products() -> JSONResponse:
    products, using_fallback = await load_products()
    return JSONResponse({"products": products, "fallback": using_fallback})


@app.post("/api/pay/{chain}")
async def pay_chain(chain: str, request: Request) -> JSONResponse:
    if chain not in {"solana", "ton"}:
        return JSONResponse({"error": "Unsupported chain."}, status_code=400)

    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON payload."}, status_code=400)

    async with httpx.AsyncClient(timeout=12.0) as client:
        try:
            response = await client.post(
                STORE_PAYMENTS_URL,
                json={**payload, "chain": chain},
                headers={"Accept": "application/json"},
            )
        except httpx.RequestError:
            return JSONResponse({"error": "Payment verifier unavailable."}, status_code=503)

    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        return JSONResponse(response.json(), status_code=response.status_code)
    return JSONResponse({"error": response.text or "Payment verification failed."}, status_code=response.status_code)


@app.post("/api/ai/generate-ui")
async def generate_ui(request: Request) -> JSONResponse:
    payload = await request.json()
    body = {
        "component_type": payload.get("componentType", "card"),
        "theme": "modern",
        "features": ["responsive", "accessible"],
        "brand_name": "Ekioba",
        "description": payload.get("description", ""),
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            response = await client.post(f"{AI_ASSISTANT_URL}/generate-ui", json=body)
            response.raise_for_status()
            data = response.json()
        except Exception:
            data = {
                "markup": f"<div class='generated-fallback'>Generated fallback for: {payload.get('description', 'request')}</div>",
            }

    return JSONResponse({"component": {"markup": data.get("markup", "")}})


@app.post("/api/ai/generate-layout")
async def generate_layout(request: Request) -> JSONResponse:
    payload = await request.json()
    body = {
        "description": payload.get("description", ""),
        "context": payload.get("context", "ekioba-marketplace"),
        "format": "html-layout",
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            response = await client.post(f"{AI_ASSISTANT_URL}/generate-ui", json=body)
            response.raise_for_status()
            data = response.json()
            layout = [{"type": "markup", "children": data.get("markup", "")}]
        except Exception:
            layout = [{"type": "card", "children": "AI layout generation unavailable."}]

    return JSONResponse({"layout": layout})


@app.post("/api/chat/proxy", response_class=HTMLResponse)
async def chat_proxy(message: str = Form(default="")) -> HTMLResponse:
    text = message.strip()
    if not text:
        return HTMLResponse('<div class="chat-bubble bot">Ask Iyobo anything about EKIOBA.</div>')

    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            response = await client.post(f"{AI_ASSISTANT_URL}{FRONTEND_IYOBO_URL}", json={"message": text})
            response.raise_for_status()
            data = response.json()
            reply = data.get("reply") or data.get("error") or "Iyobo has no response right now."
        except Exception:
            reply = "Failed to connect to Iyobo service."

    return HTMLResponse(f'<div class="chat-bubble bot">{reply}</div>')


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.get("/{filename}")
async def public_root_files(filename: str):
    # Keep existing root-level public assets (manifest, token metadata) compatible.
    candidate = PUBLIC_DIR / filename
    if candidate.exists() and candidate.is_file():
        return FileResponse(candidate)
    return JSONResponse({"error": "Not found"}, status_code=404)
