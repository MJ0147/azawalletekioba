from __future__ import annotations

import json
import os
import random
import re
import sys
import importlib.util
from datetime import datetime, timezone
from html import escape, unescape
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, Form, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Load .env before any module reads os.getenv(). load_dotenv() does not
# override variables that are already set, so host-provided settings still
# win in production; this only fills the gaps for local development.
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # python-dotenv is optional at runtime
    pass

# Make the frontend's own modules (agent, services, app/) importable no matter
# which directory the server is started from — Vercel imports this file as the
# entrypoint rather than running it from inside frontend/.
_SVC_DIR = Path(__file__).resolve().parent
if str(_SVC_DIR) not in sys.path:
    sys.path.insert(0, str(_SVC_DIR))

_APP_FEATURE_DIR = _SVC_DIR / "app"
if str(_APP_FEATURE_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_FEATURE_DIR))

from agent import get_dashboard_forecast
from services.ton import TonServiceError

BASE_DIR = Path(__file__).resolve().parent
PUBLIC_DIR = BASE_DIR / "public"

# Defensive startup: ensure expected asset folders exist so a cold start does
# not crash on an incomplete deployment package. Serverless filesystems such as
# Vercel's are read-only, so a folder that cannot be created is not fatal.
for _asset_dir in (BASE_DIR / "static", PUBLIC_DIR):
    try:
        _asset_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass

app = FastAPI(title="Ekioba Frontend")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static"), check_dir=False), name="static")

# public/ (PWA manifest, token metadata) is served at root URLs by
# `public_root_files` below, and directly by Vercel's CDN. It must not also be
# mounted with app.mount(): Vercel handles that folder at the platform level.

STORE_BACKEND_URL = os.getenv("STORE_BACKEND_URL", "http://localhost:8001/api/products/")
STORE_PAYMENTS_URL = os.getenv("STORE_PAYMENTS_URL", "http://localhost:8001/payments/process/")
AI_ASSISTANT_URL = os.getenv("AI_ASSISTANT_URL", "http://localhost:8005")
LANGUAGE_ACADEMY_URL = os.getenv("LANGUAGE_ACADEMY_URL", "http://localhost:8004")
HOTELS_SERVICE_URL = os.getenv("HOTELS_SERVICE_URL", "http://localhost:8003")
CARGO_SERVICE_URL = os.getenv("CARGO_SERVICE_URL", "http://localhost:8002")
NEXT_PUBLIC_IYOBO_API_URL = os.getenv("NEXT_PUBLIC_IYOBO_API_URL", "")
NEXT_PUBLIC_CAPILOT_API_KEY = os.getenv("NEXT_PUBLIC_CAPILOT_API_KEY", "")
FRONTEND_IYOBO_URL = os.getenv("FRONTEND_IYOBO_URL", "/chat")
TON_MERCHANT_WALLET = os.getenv("TON_MERCHANT_WALLET", "")
# Absolute origin used for the TON Connect manifest. Leave empty to derive
# it from the incoming request (correct behind a reverse proxy too).
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
IDIA_NGN_RATE = float(os.getenv("IDIA_NGN_RATE", "30.0"))


def _default_forecast_payload() -> dict[str, Any]:
    return {
        "stocks": {"labels": [], "actual": [], "predicted": []},
        "crypto": {"labels": [], "actual": [], "predicted": []},
        "sentiment": {"labels": ["Market"], "values": [50]},
        "cloud": {"labels": [], "values": []},
    }


def _is_api_request(request: Request) -> bool:
    path = request.url.path or ""
    accept = request.headers.get("accept", "").lower()
    return path.startswith("/api/") or "application/json" in accept


async def _safe_dashboard_forecast() -> dict[str, Any]:
    try:
        payload = await get_dashboard_forecast()
        if isinstance(payload, dict):
            return payload
    except Exception:
        pass
    return _default_forecast_payload()


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    if _is_api_request(request):
        return JSONResponse({"error": "Invalid request data.", "details": exc.errors()}, status_code=422)
    return templates.TemplateResponse(
        "error.html",
        {
            "request": request,
            "status_code": 400,
            "message": "The request could not be processed. Please check your input and try again.",
        },
        status_code=400,
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if _is_api_request(request):
        detail = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return JSONResponse({"error": detail}, status_code=exc.status_code)

    message = "Page not found."
    if exc.status_code >= 500:
        message = "Service temporarily unavailable. Please try again shortly."
    elif exc.status_code == 403:
        message = "You are not allowed to access this page."

    return templates.TemplateResponse(
        "error.html",
        {
            "request": request,
            "status_code": exc.status_code,
            "message": message,
        },
        status_code=exc.status_code,
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    if _is_api_request(request):
        return JSONResponse({"error": "Service temporarily unavailable."}, status_code=500)
    return templates.TemplateResponse(
        "error.html",
        {
            "request": request,
            "status_code": 500,
            "message": "Service temporarily unavailable. Please try again shortly.",
        },
        status_code=500,
    )


def _build_ai_headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if NEXT_PUBLIC_CAPILOT_API_KEY:
        headers["Authorization"] = f"Bearer {NEXT_PUBLIC_CAPILOT_API_KEY}"
    return headers


def _resolve_ai_base_url() -> str:
    base = (NEXT_PUBLIC_IYOBO_API_URL or AI_ASSISTANT_URL).strip()
    return base.rstrip("/")


def _resolve_chat_url() -> str:
    base = _resolve_ai_base_url()
    if base.endswith("/api/ai"):
        base = base[:-7]
    return f"{base}/chat"


_URL_RE = re.compile(r"https?://[^\s<>()\"']+", re.IGNORECASE)


def _summarize_html(html_text: str, max_chars: int = 420) -> tuple[str, str]:
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html_text, flags=re.IGNORECASE | re.DOTALL)
    title = unescape(title_match.group(1).strip()) if title_match else "Web page"

    cleaned = re.sub(r"<script[\s\S]*?</script>", " ", html_text, flags=re.IGNORECASE)
    cleaned = re.sub(r"<style[\s\S]*?</style>", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = unescape(re.sub(r"\s+", " ", cleaned)).strip()
    snippet = cleaned[:max_chars] + ("..." if len(cleaned) > max_chars else "")
    return title[:140], snippet


async def _extract_link_search_results(text: str) -> list[dict[str, str]]:
    urls = []
    for match in _URL_RE.findall(text or ""):
        url = match.rstrip('.,;:)!?>\"]')
        if url not in urls:
            urls.append(url)

    if not urls:
        return []

    results: list[dict[str, str]] = []
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        for url in urls[:3]:
            try:
                response = await client.get(url, headers={"User-Agent": "EKIOBA-Iyobo/1.0", "Accept": "text/html,application/xhtml+xml"})
                content_type = response.headers.get("content-type", "").lower()
                if "text/html" not in content_type:
                    snippet = (response.text or "")[:220]
                    results.append({"name": url, "url": str(response.url), "snippet": snippet})
                    continue

                title, snippet = _summarize_html(response.text)
                results.append({"name": title or url, "url": str(response.url), "snippet": snippet or "No readable summary extracted."})
            except Exception:
                continue

    return results


def _get_payment_handlers():
    module_path = BASE_DIR / "app" / "api" / "pay" / "paymentHandler.py"
    spec = importlib.util.spec_from_file_location("ekioba_payment_handler", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Payment handler module could not be loaded.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.create_ton_payment_request

FALLBACK_PRODUCTS: list[dict[str, Any]] = [
    # Gold Collection
    {
        "id": "gold-1",
        "name": "Golden Pendant - Oba Ozolua",
        "description": "18K Gold plated pendant inspired by classic Edo bronze casting.",
        "price": 45000,
        "category": "gold",
        "image": "https://olive-adorable-cephalopod-171.mypinata.cloud/ipfs/bafkreiahf52abfi6nzgnkhw5i2gcvxap4aszgk254lqt4qx6wzgnewwrhy",
    },
    {
        "id": "gold-2",
        "name": "Gold Collection - Royal Set",
        "description": "Complete royal gold jewelry set with traditional Edo craftsmanship.",
        "price": 150000,
        "category": "gold",
        "image": "https://olive-adorable-cephalopod-171.mypinata.cloud/ipfs/bafybeic3xqlbjcx22doceugjwke3m4ckuxdckmabni2bwo34o6ecajel5m/IMG_E1270.JPG",
    },
    {
        "id": "gold-3",
        "name": "White Gold",
        "description": "Elegant white gold jewelry crafted with timeless Edo-inspired detail.",
        "price": 89000,
        "category": "gold",
        "image": "https://olive-adorable-cephalopod-171.mypinata.cloud/ipfs/bafybeic3xqlbjcx22doceugjwke3m4ckuxdckmabni2bwo34o6ecajel5m/IMG_E1281.JPG",
    },
    # Regular Collection
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
        "image": "https://olive-adorable-cephalopod-171.mypinata.cloud/ipfs/bafybeicqkclmtsxhzsazrqd4qtr3byuxpeshgwasknsfnzqrnys6xbo3uq/Palm%20Oil%20Okomu.jpeg",
    },
]

PRESTIGIOUS_HOTELS: list[dict[str, Any]] = [
    {
        "id": 101,
        "title": "Protea Hotel Benin City Select Emotan",
        "city": "Benin City",
        "price_per_night": "135000.00",
        "available": True,
        "rating": 4.6,
        "description": "Premium business-class comfort in the heart of Benin City.",
    },
    {
        "id": 102,
        "title": "Oti Hotels Benin",
        "city": "Benin City",
        "price_per_night": "85000.00",
        "available": True,
        "rating": 4.3,
        "description": "Modern hospitality with event and executive facilities.",
    },
        {
            "id": 103,
            "title": "Garki Hotel Benin City",
            "city": "Benin City",
            "price_per_night": "65000.00",
            "available": True,
            "rating": 4.1,
            "description": "Comfortable city-centre hotel popular with business travellers visiting the Benin Kingdom.",
        },
        {
            "id": 104,
            "title": "Heritage Luxury Suites Benin",
            "city": "Benin City",
            "price_per_night": "115000.00",
            "available": True,
            "rating": 4.5,
            "description": "Boutique suites celebrating Benin Kingdom décor — full amenities and cultural immersion.",
        },
        {
            "id": 201,
        "title": "Transcorp Hilton Abuja",
        "city": "Abuja",
        "price_per_night": "280000.00",
        "available": True,
        "rating": 4.8,
        "description": "Iconic five-star hotel with premium dining and conference experience.",
    },
    {
        "id": 202,
        "title": "Fraser Suites Abuja",
        "city": "Abuja",
        "price_per_night": "240000.00",
        "available": True,
        "rating": 4.7,
        "description": "Luxury serviced apartments ideal for business and long stays.",
    },
    {
        "id": 301,
        "title": "Eko Hotels & Suites",
        "city": "Lagos",
        "price_per_night": "220000.00",
        "available": True,
        "rating": 4.7,
        "description": "Prestigious Lagos waterfront hospitality and events destination.",
    },
    {
        "id": 302,
        "title": "The Wheatbaker Lagos",
        "city": "Lagos",
        "price_per_night": "260000.00",
        "available": True,
        "rating": 4.8,
        "description": "Luxury boutique experience in the heart of Ikoyi.",
    },
    {
        "id": 401,
        "title": "Hotel Presidential Port Harcourt",
        "city": "Port Harcourt",
        "price_per_night": "145000.00",
        "available": True,
        "rating": 4.5,
        "description": "Established premium hotel with excellent city access.",
    },
    {
        "id": 402,
        "title": "Novotel Port Harcourt",
        "city": "Port Harcourt",
        "price_per_night": "125000.00",
        "available": True,
        "rating": 4.4,
        "description": "Business-focused comfort with dependable service standards.",
    },
]

ACADEMY_WORD_BANK: list[dict[str, str]] = [
    # ── Greetings ──────────────────────────────────────────────────────────
    {"edo": "Koyo", "english": "Hello", "category": "greetings"},
    {"edo": "Otabor", "english": "Good morning", "category": "greetings"},
    {"edo": "Vbe ighe", "english": "Good afternoon", "category": "greetings"},
    {"edo": "Vbe oyi", "english": "Good evening", "category": "greetings"},
    {"edo": "Obo", "english": "Thank you", "category": "greetings"},
    {"edo": "Vbe", "english": "Come", "category": "greetings"},
    {"edo": "Laro", "english": "Goodbye", "category": "greetings"},
    {"edo": "Ege", "english": "Please", "category": "greetings"},
    {"edo": "Mwen", "english": "I / Me", "category": "greetings"},
    {"edo": "Iro", "english": "You", "category": "greetings"},
    {"edo": "Iran", "english": "They / Them", "category": "greetings"},
    {"edo": "Imina", "english": "My name is", "category": "greetings"},
    {"edo": "Rẹn", "english": "He / She / It", "category": "greetings"},
    # ── Numbers ────────────────────────────────────────────────────────────
    {"edo": "Ovbokhan", "english": "One", "category": "numbers"},
    {"edo": "Eva", "english": "Two", "category": "numbers"},
    {"edo": "Eha", "english": "Three", "category": "numbers"},
    {"edo": "Ene", "english": "Four", "category": "numbers"},
    {"edo": "Isen", "english": "Five", "category": "numbers"},
    {"edo": "Eissen", "english": "Six", "category": "numbers"},
    {"edo": "Ihien", "english": "Seven", "category": "numbers"},
    {"edo": "Eren", "english": "Eight", "category": "numbers"},
    {"edo": "Ehen", "english": "Nine", "category": "numbers"},
    {"edo": "Igbe", "english": "Ten", "category": "numbers"},
    {"edo": "Igbe ne eva", "english": "Twenty", "category": "numbers"},
    {"edo": "Igbe ne eha", "english": "Thirty", "category": "numbers"},
    {"edo": "Iguegbe", "english": "Hundred", "category": "numbers"},
    {"edo": "Egbe", "english": "Time", "category": "numbers"},
    # ── Food & Drink ───────────────────────────────────────────────────────
    {"edo": "Evbare", "english": "Food", "category": "food"},
    {"edo": "Emwin", "english": "Water", "category": "food"},
    {"edo": "Obe", "english": "Soup", "category": "food"},
    {"edo": "Oka", "english": "Maize / Corn", "category": "food"},
    {"edo": "Eme", "english": "Meat", "category": "food"},
    {"edo": "Okpo", "english": "Fish", "category": "food"},
    {"edo": "Ose", "english": "Pepper", "category": "food"},
    {"edo": "Ogede", "english": "Banana", "category": "food"},
    {"edo": "Oran", "english": "Palm oil", "category": "food"},
    {"edo": "Ukodo", "english": "Yam pepper soup", "category": "food"},
    {"edo": "Ehiyo", "english": "Salt", "category": "food"},
    {"edo": "Akhere", "english": "Bowl / Plate", "category": "food"},
    {"edo": "Ema", "english": "Pounded yam", "category": "food"},
    {"edo": "Ọkpọ ẹdo", "english": "Smoked fish", "category": "food"},
    # ── Family ─────────────────────────────────────────────────────────────
    {"edo": "Erha", "english": "Father", "category": "family"},
    {"edo": "Iye", "english": "Mother", "category": "family"},
    {"edo": "Omomo", "english": "Child", "category": "family"},
    {"edo": "Ozo", "english": "Husband", "category": "family"},
    {"edo": "Okhuo", "english": "Wife / Woman", "category": "family"},
    {"edo": "Odion", "english": "First born / Elder", "category": "family"},
    {"edo": "Omuogun", "english": "Brother", "category": "family"},
    {"edo": "Eno", "english": "Sister", "category": "family"},
    {"edo": "Isen erha", "english": "Grandfather", "category": "family"},
    {"edo": "Isen iye", "english": "Grandmother", "category": "family"},
    {"edo": "Ọmọ ozo", "english": "Son", "category": "family"},
    {"edo": "Ọmọ okhuo", "english": "Daughter", "category": "family"},
    # ── Nature ─────────────────────────────────────────────────────────────
    {"edo": "Uwa", "english": "World", "category": "nature"},
    {"edo": "Iwin", "english": "Sun", "category": "nature"},
    {"edo": "Ukpoba", "english": "River", "category": "nature"},
    {"edo": "Ude", "english": "Road / Path", "category": "nature"},
    {"edo": "Ekpen", "english": "Leopard", "category": "nature"},
    {"edo": "Okpan", "english": "Bird", "category": "nature"},
    {"edo": "Erhen", "english": "Tree", "category": "nature"},
    {"edo": "Ikpe", "english": "Rain", "category": "nature"},
    {"edo": "Ede", "english": "Day", "category": "nature"},
    {"edo": "Evbi", "english": "Night", "category": "nature"},
    {"edo": "Oto", "english": "Earth / Ground", "category": "nature"},
    {"edo": "Azagba", "english": "Forest / Bush", "category": "nature"},
    {"edo": "Aro", "english": "Eye / Face", "category": "nature"},
    {"edo": "Odẹ", "english": "Farm / Field", "category": "nature"},
    # ── Culture & History ──────────────────────────────────────────────────
    {"edo": "Osa", "english": "God", "category": "culture"},
    {"edo": "Osanobua", "english": "Almighty God", "category": "culture"},
    {"edo": "Oghene", "english": "King", "category": "culture"},
    {"edo": "Oba", "english": "Paramount Ruler", "category": "culture"},
    {"edo": "Idia", "english": "First Queen Mother", "category": "culture"},
    {"edo": "Igue", "english": "Royal Festival", "category": "culture"},
    {"edo": "Ivie", "english": "Coral beads", "category": "culture"},
    {"edo": "Ekhoe", "english": "Ceremonial gong", "category": "culture"},
    {"edo": "Ẹdo", "english": "Benin Kingdom", "category": "culture"},
    {"edo": "Igun", "english": "Bronze casting guild", "category": "culture"},
    {"edo": "Iyoba", "english": "Queen Mother", "category": "culture"},
    {"edo": "Ewuare", "english": "Great reformer Oba", "category": "culture"},
    {"edo": "Ozolua", "english": "The Conqueror Oba", "category": "culture"},
    {"edo": "Esigie", "english": "Oba who fought the Igala", "category": "culture"},
    # ── Body ───────────────────────────────────────────────────────────────
    {"edo": "Okpa", "english": "Leg / Foot", "category": "body"},
    {"edo": "Uwu", "english": "Arm / Hand", "category": "body"},
    {"edo": "Uhunmwun", "english": "Head", "category": "body"},
    {"edo": "Unu", "english": "Mouth", "category": "body"},
    {"edo": "Ihe", "english": "Ear", "category": "body"},
    {"edo": "Egbe", "english": "Body", "category": "body"},
    {"edo": "Ehe", "english": "Nose", "category": "body"},
    {"edo": "Oha", "english": "Back", "category": "body"},
    {"edo": "Ọkọ", "english": "Heart / Chest", "category": "body"},
    # ── Home & Objects ─────────────────────────────────────────────────────
    {"edo": "Owie", "english": "House", "category": "home"},
    {"edo": "Eke", "english": "Chair / Seat", "category": "home"},
    {"edo": "Oton", "english": "Bed", "category": "home"},
    {"edo": "Akhe", "english": "Pot / Vessel", "category": "home"},
    {"edo": "Ikhue", "english": "Door", "category": "home"},
    {"edo": "Aro owie", "english": "Window", "category": "home"},
    {"edo": "Urho", "english": "Gate / Entrance", "category": "home"},
]


def _load_updated_academy_word_bank() -> list[dict[str, str]]:
    category_aliases = {
        "greeting": "greetings",
        "gratitude": "greetings",
        "verb": "verbs",
        "verb_phrase": "verbs",
        "auxiliary": "verbs",
        "negation": "grammar",
        "particle": "grammar",
        "question": "grammar",
        "noun": "general",
    }
    candidates = [
        BASE_DIR / "public" / "edo_vocab.json",
        BASE_DIR / "data" / "edo_vocab.json",
        BASE_DIR / "app" / "data" / "edo_vocab.json",
        BASE_DIR.parent / "language_academy" / "app" / "data" / "edo_vocab.json",
    ]
    for path in candidates:
        try:
            if not path.exists():
                continue
            with path.open("r", encoding="utf-8") as handle:
                raw = json.load(handle)
            if not isinstance(raw, list):
                continue

            words: list[dict[str, str]] = []
            for item in raw:
                if not isinstance(item, dict):
                    continue
                edo = str(item.get("edo", "")).strip()
                english = str(item.get("english", "")).strip()
                if not edo or not english:
                    continue
                words.append(
                    {
                        "edo": edo,
                        "english": english,
                        "category": category_aliases.get(
                            str(item.get("category", "general")).strip().lower(),
                            str(item.get("category", "general")).strip().lower() or "general",
                        ),
                    }
                )

            if words:
                return words
        except Exception:
            continue
    return []


_UPDATED_ACADEMY_WORD_BANK = _load_updated_academy_word_bank()
if _UPDATED_ACADEMY_WORD_BANK:
    ACADEMY_WORD_BANK = _UPDATED_ACADEMY_WORD_BANK


def _academy_vocab_filtered(search: str = "", category: str = "") -> list[dict[str, str]]:
    search_l = (search or "").strip().lower()
    category_l = (category or "").strip().lower()
    items: list[dict[str, str]] = []
    for item in ACADEMY_WORD_BANK:
        if category_l and item.get("category", "").lower() != category_l:
            continue
        if search_l and search_l not in item.get("edo", "").lower() and search_l not in item.get("english", "").lower():
            continue
        items.append(item)
    return items


def _build_quiz_section(size: int = 50, category: str = "") -> list[dict[str, Any]]:
    base = _academy_vocab_filtered(category=category) or ACADEMY_WORD_BANK
    target_size = max(1, min(size, 50))
    all_english = [w["english"] for w in ACADEMY_WORD_BANK]
    all_edo = [w["edo"] for w in ACADEMY_WORD_BANK]
    questions: list[dict[str, Any]] = []
    seen: set[str] = set()

    # First pass: unique Edo→English and English→Edo questions
    attempts = 0
    while len(questions) < target_size and attempts < target_size * 6:
        attempts += 1
        word = random.choice(base)
        q_type = "en_to_edo" if random.random() < 0.5 else "edo_to_en"
        key = f"{word['edo']}:{q_type}"
        if key in seen:
            continue
        seen.add(key)

        if q_type == "edo_to_en":
            correct = word["english"]
            wrong_pool = [x for x in all_english if x != correct]
            random.shuffle(wrong_pool)
            choices = [correct] + wrong_pool[:3]
            random.shuffle(choices)
            prompt = f"What is the English meaning of the Edo word '{word['edo']}'?"
        else:
            correct = word["edo"]
            wrong_pool = [x for x in all_edo if x != correct]
            random.shuffle(wrong_pool)
            choices = [correct] + wrong_pool[:3]
            random.shuffle(choices)
            prompt = f"How do you say '{word['english']}' in Edo?"

        labels = ["A", "B", "C", "D"]
        options = [{"label": labels[i], "text": choices[i]} for i in range(len(choices))]
        questions.append({
            "prompt": prompt,
            "answer": correct,
            "category": word.get("category", "general"),
            "options": options,
        })

    # Second pass: fill remaining slots (allow repeats when bank is small)
    extra = 0
    while len(questions) < target_size and extra < target_size:
        extra += 1
        word = random.choice(base)
        q_type = "en_to_edo" if random.random() < 0.5 else "edo_to_en"
        if q_type == "edo_to_en":
            correct = word["english"]
            wrong_pool = [x for x in all_english if x != correct]
            random.shuffle(wrong_pool)
            choices = [correct] + wrong_pool[:3]
            random.shuffle(choices)
            prompt = f"What is the English meaning of the Edo word '{word['edo']}'?"
        else:
            correct = word["edo"]
            wrong_pool = [x for x in all_edo if x != correct]
            random.shuffle(wrong_pool)
            choices = [correct] + wrong_pool[:3]
            random.shuffle(choices)
            prompt = f"How do you say '{word['english']}' in Edo?"
        labels = ["A", "B", "C", "D"]
        options = [{"label": labels[i], "text": choices[i]} for i in range(len(choices))]
        questions.append({
            "prompt": prompt,
            "answer": correct,
            "category": word.get("category", "general"),
            "options": options,
        })

    return questions[:target_size]

async def load_products() -> tuple[list[dict[str, Any]], bool]:
    def _extract_products(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return payload
        if not isinstance(payload, dict):
            return []

        for key in ("products", "results", "items", "data"):
            candidate = payload.get(key)
            if isinstance(candidate, list):
                return candidate
            if isinstance(candidate, dict):
                for inner_key in ("products", "results", "items", "data"):
                    inner = candidate.get(inner_key)
                    if isinstance(inner, list):
                        return inner
        return []

    store_urls = [STORE_BACKEND_URL]

    remote_products: list[dict[str, Any]] = []
    for store_url in store_urls:
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.get(store_url, headers={"Accept": "application/json"})
                response.raise_for_status()
                payload = response.json()
                extracted = _extract_products(payload)
                if extracted:
                    remote_products = extracted
                    break
        except Exception:
            continue

    if not remote_products:
        return FALLBACK_PRODUCTS, True

    # Keep backend products first, then append missing fallback products
    # (including Gold Collection) so catalog completeness is guaranteed.
    merged: list[dict[str, Any]] = list(remote_products)
    seen_ids: set[str] = set()
    seen_names: set[str] = set()
    for item in remote_products:
        item_id = str(item.get("id") or "").strip().lower()
        item_name = str(item.get("name") or "").strip().lower()
        if item_id:
            seen_ids.add(item_id)
        if item_name:
            seen_names.add(item_name)

    for fallback in FALLBACK_PRODUCTS:
        fallback_id = str(fallback.get("id") or "").strip().lower()
        fallback_name = str(fallback.get("name") or "").strip().lower()
        if (fallback_id and fallback_id in seen_ids) or (fallback_name and fallback_name in seen_names):
            continue
        if fallback_id or fallback_name:
            merged.append(fallback)
            if fallback_id:
                seen_ids.add(fallback_id)
            if fallback_name:
                seen_names.add(fallback_name)

    return merged, False


def category_distribution(products: list[dict[str, Any]]) -> dict[str, int]:
    buckets: dict[str, int] = {}
    for product in products:
        key = str(product.get("category") or "other")
        buckets[key] = buckets.get(key, 0) + 1
    return buckets


async def _service_status(name: str, base_url: str, health_paths: list[str], detail_url: str) -> dict[str, Any]:
    status_payload: dict[str, Any] = {
        "name": name,
        "online": False,
        "detail": "offline",
        "detail_url": detail_url,
        "sample_size": 0,
    }
    normalized = (base_url or "").strip().rstrip("/")
    if not normalized:
        status_payload["detail"] = "missing URL"
        return status_payload

    async with httpx.AsyncClient(timeout=8.0) as client:
        for path in health_paths:
            try:
                response = await client.get(f"{normalized}{path}", headers={"Accept": "application/json"})
                if response.status_code < 400:
                    status_payload["online"] = True
                    status_payload["detail"] = "live"
                    break
            except Exception:
                continue

        if name == "Edo Academy" and status_payload["online"]:
            try:
                vocab = await client.get(f"{normalized}/vocabulary?limit=3", headers={"Accept": "application/json"})
                vocab.raise_for_status()
                items = vocab.json().get("items", [])
                if isinstance(items, list):
                    status_payload["sample_size"] = len(items)
            except Exception:
                pass

        if name == "Hotel Service" and status_payload["online"]:
            try:
                listings = await client.get(f"{normalized}/api/listings/", headers={"Accept": "application/json"})
                listings.raise_for_status()
                data = listings.json()
                if isinstance(data, list):
                    status_payload["sample_size"] = len(data)
            except Exception:
                pass

    return status_payload


async def get_platform_services_status() -> dict[str, Any]:
    academy = await _service_status(
        "Edo Academy",
        LANGUAGE_ACADEMY_URL,
        ["/health"],
        "/academy",
    )
    hotels = await _service_status(
        "Hotel Service",
        HOTELS_SERVICE_URL,
        ["/health", "/health/"],
        "/hotels",
    )
    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "services": [academy, hotels],
    }


@app.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    products, using_fallback = await load_products()
    chart_data = category_distribution(products)
    forecast = await _safe_dashboard_forecast()
    idia_ngn_rate = IDIA_NGN_RATE if IDIA_NGN_RATE > 0 else 30.0
    context = {
        "request": request,
        "forecast": forecast,
        "products": products,
        "idia_ngn_rate": idia_ngn_rate,
        "using_fallback": using_fallback,
        "products_json": json.dumps(products),
        "chart_labels": list(chart_data.keys()),
        "chart_values": list(chart_data.values()),
        "iyobo_url": FRONTEND_IYOBO_URL,
        "ton_wallet": TON_MERCHANT_WALLET,
    }
    return templates.TemplateResponse("index.html", context)


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    return RedirectResponse(url="/", status_code=307)


@app.get("/wallet-dashboard", response_class=HTMLResponse)
async def wallet_dashboard_html(request: Request) -> HTMLResponse:
    return RedirectResponse(url="/", status_code=307)


async def _dashboard_payload() -> JSONResponse:
    return JSONResponse(await _safe_dashboard_forecast())


@app.get("/api/dashboard")
async def dashboard_data() -> JSONResponse:
    return await _dashboard_payload()


@app.get("/api/dashboard/forecast")
async def dashboard_forecast() -> JSONResponse:
    return await _dashboard_payload()


@app.get("/api/wallet/dashboard")
async def wallet_dashboard() -> JSONResponse:
    """Wallet dashboard endpoint with forecast data and predictions."""
    forecast = await _safe_dashboard_forecast()
    return JSONResponse({
        "wallet": {
            "chains": ["ton"],
            "ton_wallet": TON_MERCHANT_WALLET,
        },
        "forecast": forecast,
        "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
    })


@app.get("/partials/products", response_class=HTMLResponse)
async def products_partial(request: Request) -> HTMLResponse:
    products, using_fallback = await load_products()
    idia_ngn_rate = IDIA_NGN_RATE if IDIA_NGN_RATE > 0 else 30.0
    return templates.TemplateResponse(
        "partials/products_grid.html",
        {
            "request": request,
            "products": products,
            "using_fallback": using_fallback,
            "idia_ngn_rate": idia_ngn_rate,
        },
    )


@app.get("/api/store/products")
async def store_products() -> JSONResponse:
    products, using_fallback = await load_products()
    return JSONResponse({"products": products, "fallback": using_fallback})


@app.post("/api/pay/{chain}")
async def pay_chain(chain: str, request: Request) -> JSONResponse:
    if chain != "ton":
        return JSONResponse(
            {"error": "Unsupported chain. EKIOBA settles IDIA on TON only."},
            status_code=400,
        )

    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON payload."}, status_code=400)

    try:
        create_ton_payment_request = _get_payment_handlers()
    except Exception:
        return JSONResponse({"error": "Payment service unavailable."}, status_code=503)

    price_ngn = float(payload.get("price_ngn") or payload.get("price") or payload.get("cart_total_ngn") or 0)
    cart_items = payload.get("cart_items") if isinstance(payload.get("cart_items"), list) else []
    is_cart_checkout = bool(payload.get("is_cart_checkout")) or bool(cart_items)
    if is_cart_checkout:
        item_count = len(cart_items)
        product_name = f"EKIOBA Cart Checkout ({item_count} item{'s' if item_count != 1 else ''})"
    else:
        product_name = str(payload.get("product_name") or payload.get("name") or "EKIOBA Product")

    if price_ngn <= 0:
        return JSONResponse({"error": "Invalid price."}, status_code=422)

    try:
        result = await create_ton_payment_request(
            price_ngn,
            product_name,
            cart_items=cart_items,
            is_cart_checkout=is_cart_checkout,
            sender_address=payload.get("sender_address"),
        )
    except ValueError as exc:
        # Missing/invalid merchant configuration.
        return JSONResponse({"error": str(exc)}, status_code=503)
    except TonServiceError as exc:
        # The TON API could not be reached or returned something unusable.
        return JSONResponse({"error": str(exc)}, status_code=502)
    except Exception:
        return JSONResponse({"error": "Payment request failed."}, status_code=500)

    # Best-effort bookkeeping: a Supabase outage must not fail a checkout.
    from services import orders

    result["recorded"] = await orders.record(result, status="pending")

    return JSONResponse(result)


@app.post("/api/pay/ton/verify")
async def verify_ton_pay(request: Request) -> JSONResponse:
    """
    Confirm a stored order against the chain.

    Nothing that decides the outcome comes from the caller: the merchant
    wallet is server config, and the expected amount and comment come from the
    stored order. A caller cannot confirm an order with a transfer to their own
    wallet, or with a payment made for a different order.
    """
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON."}, status_code=400)

    order_id = str(payload.get("order_id") or "").strip()
    if not order_id:
        return JSONResponse({"error": "order_id is required."}, status_code=422)

    from services import orders
    from services.ton import verify_jetton_payment

    if not orders.is_enabled():
        return JSONResponse(
            {"error": "Order verification is unavailable."}, status_code=503
        )

    order = await orders.get(order_id)
    if order is None:
        return JSONResponse({"error": "Order not found."}, status_code=404)

    if order.get("status") == "confirmed":
        return JSONResponse({
            "verified": True,
            "order_id": order_id,
            "tx_hash": order.get("tx_hash"),
            "status": "confirmed",
        })

    try:
        result = await verify_jetton_payment(
            TON_MERCHANT_WALLET,
            f"EKIOBA-{order_id}",
            float(order.get("amount_idia") or 0),
            tx_hash=payload.get("tx_hash") or None,
        )
    except TonServiceError as exc:
        return JSONResponse({"error": str(exc)}, status_code=502)

    if result.get("verified"):
        await orders.set_status(order_id, "confirmed", tx_hash=result["tx_hash"])

    result["order_id"] = order_id
    return JSONResponse(result)


def _site_origin(request: Request) -> str:
    """
    Absolute origin of this deployment.

    TON wallets reject a manifest whose `url` does not match the origin that
    asked for the connection, so it can never be hardcoded. Prefer an explicit
    PUBLIC_BASE_URL, else rebuild it from the X-Forwarded-* proxy headers.
    """
    if PUBLIC_BASE_URL:
        return PUBLIC_BASE_URL

    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    scheme = (forwarded_proto.split(",")[0].strip() or request.url.scheme or "https")

    host = (
        request.headers.get("x-forwarded-host")
        or request.headers.get("host")
        or request.url.netloc
    )
    host = host.split(",")[0].strip()
    return f"{scheme}://{host}"


@app.get("/tonconnect-manifest.json")
async def tonconnect_manifest(request: Request) -> JSONResponse:
    """
    TON Connect dApp manifest, generated per-origin.

    Wallets fetch this cross-origin, so it must be publicly readable.
    The icon must be a real PNG — several wallets reject .ico and .svg.
    """
    origin = _site_origin(request)
    return JSONResponse(
        {
            "url": origin,
            "name": "EKIOBA",
            "iconUrl": f"{origin}/static/images/ekioba-tonconnect-icon.png",
        },
        headers={
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "public, max-age=300",
        },
    )


@app.get("/api/pay/idia-rate")
async def idia_rate() -> JSONResponse:
    """Return the current idia coin NGN exchange rate and where it came from."""
    from services.idiaTokenService import (
        fetch_idia_ngn_rate,
        fetch_idia_usdt_rate,
        get_last_fx_source,
        get_last_rate_source,
        get_last_usdt_ngn_rate,
        IDIA_TON_JETTON_ADDRESS,
    )
    rate = await fetch_idia_ngn_rate()
    usdt = await fetch_idia_usdt_rate()
    source = get_last_rate_source()
    fx_source = get_last_fx_source()
    return JSONResponse({
        "ngn_per_idia": rate,
        "usdt_per_idia": usdt,
        "ngn_per_usdt": get_last_usdt_ngn_rate(),
        "ton_jetton": IDIA_TON_JETTON_ADDRESS,
        "chains": ["ton"],
        # "dedust" means a real market price; "fallback" means the configured
        # placeholder, i.e. no TON/IDIA pool exists yet.
        "source": source,
        "live": source != "fallback",
        # The USDT->NGN leg is sourced separately: "flutterwave" is live FX,
        # "static" is the configured USDT_NGN_RATE.
        "fx_source": fx_source,
        "fx_live": fx_source != "static",
    })


@app.get("/api/pay/dedust-market")
async def dedust_market() -> JSONResponse:
    """DeDust pool diagnostics for IDIA — pool address, reserves, derived prices."""
    from services import dedust

    try:
        return JSONResponse(await dedust.get_market_snapshot())
    except Exception as exc:
        return JSONResponse({"error": str(exc), "source": "dedust"}, status_code=502)


@app.get("/todos", response_class=HTMLResponse)
async def todos_page() -> HTMLResponse:
    """List rows from the Supabase `todos` table."""
    from services import supabase_client

    try:
        todos = await supabase_client.select("todos", order="id")
    except supabase_client.SupabaseError as exc:
        return HTMLResponse(
            f"<h1>Todos</h1><p>Could not load todos: {escape(str(exc))}</p>",
            status_code=503,
        )

    items = "".join(
        f"<li>{escape(str(todo.get('name') or todo.get('title') or todo.get('id')))}</li>"
        for todo in todos
    )
    return HTMLResponse(f"<h1>Todos</h1><ul>{items}</ul>")


_ORDERS_UNAUTHORIZED = {"error": "Unauthorized."}


@app.get("/api/orders")
async def list_orders(request: Request, limit: int = 20) -> JSONResponse:
    """
    Recent IDIA orders. Admin-only: rows are read with the service-role key,
    which bypasses RLS, so the bearer token is the only thing guarding them.
    """
    from services import orders

    if not orders.is_admin(request.headers.get("authorization")):
        return JSONResponse(_ORDERS_UNAUTHORIZED, status_code=401)

    rows = await orders.recent(limit)
    return JSONResponse(
        {"orders": rows, "count": len(rows), "enabled": orders.is_enabled()}
    )


@app.get("/api/orders/{order_id}")
async def get_order(order_id: str, request: Request) -> JSONResponse:
    """A single order. Admin-only, for the same reason as `list_orders`."""
    from services import orders

    if not orders.is_admin(request.headers.get("authorization")):
        return JSONResponse(_ORDERS_UNAUTHORIZED, status_code=401)

    row = await orders.get(order_id)
    if row is None:
        return JSONResponse({"error": "Order not found."}, status_code=404)
    return JSONResponse(row)


@app.get("/api/supabase/status")
async def supabase_status(table: str | None = None) -> JSONResponse:
    """
    Supabase connectivity diagnostics.

    Reports only whether keys are *present* — never their values.
    """
    from services import supabase_client

    try:
        return JSONResponse(await supabase_client.health_check(table))
    except Exception as exc:
        return JSONResponse(
            {"error": str(exc), "source": "supabase"}, status_code=502
        )


@app.get("/api/pay/fx")
async def fx_status() -> JSONResponse:
    """Flutterwave FX diagnostics for the USDT -> NGN leg."""
    from services import flutterwave

    try:
        return JSONResponse(await flutterwave.get_fx_snapshot())
    except Exception as exc:
        return JSONResponse({"error": str(exc), "source": "flutterwave"}, status_code=502)



@app.post("/api/ai/generate-ui")
async def generate_ui(request: Request) -> JSONResponse:
    payload = await request.json()
    body = {
        "description": payload.get("description", ""),
        "componentType": payload.get("componentType", "card"),
        "context": payload.get("context", "ekioba-marketplace"),
    }
    ai_base_url = _resolve_ai_base_url()

    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            response = await client.post(
                f"{ai_base_url}/generate-ui",
                json=body,
                headers=_build_ai_headers(),
            )
            response.raise_for_status()
            data = response.json()
        except Exception:
            data = {
                "component": {
                    "type": body["componentType"],
                    "props": {"className": "generated-fallback"},
                    "children": [{"type": "span", "props": {"text": body["description"] or "Generated fallback component"}}],
                }
            }

    return JSONResponse({"component": data.get("component", data)})


@app.post("/api/ai/generate-layout")
async def generate_layout(request: Request) -> JSONResponse:
    payload = await request.json()
    body = {
        "description": payload.get("description", ""),
        "context": payload.get("context", "ekioba-marketplace"),
    }
    ai_base_url = _resolve_ai_base_url()

    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            response = await client.post(
                f"{ai_base_url}/generate-layout",
                json=body,
                headers=_build_ai_headers(),
            )
            response.raise_for_status()
            data = response.json()
        except Exception:
            layout = [{"type": "card", "props": {"text": "AI layout generation unavailable."}}]
            return JSONResponse({"layout": layout})

    return JSONResponse({"layout": data.get("layout", data)})


@app.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("chat.html", {"request": request})


_IYOBO_KNOWLEDGE: list[tuple[list[str], str]] = [
    (
        ["hello", "hi", "hey", "koyo", "obowie", "greet", "welcome", "start", "begin"],
        "Koyo! Welcome to EKIOBA — your gateway to authentic Edo and Benin Kingdom culture. I'm Iyobo, your AI cultural guide. Ask me about products, IDIA Coin payments, Edo history, the Language Academy, hotels, cargo, or anything EKIOBA. How can I help?",
    ),
    (
        ["who are you", "what are you", "iyobo", "about you", "your name", "introduce yourself"],
        "I'm Iyobo — EKIOBA's AI cultural assistant. I combine deep knowledge of the Benin Kingdom, IDIA Coin blockchain payments, and real-time market data to give you accurate, helpful answers. I can help you shop, pay, learn Edo language, book hotels, ship cargo, and understand the heritage behind every EKIOBA product.",
    ),
    (
        ["ekioba", "about ekioba", "what is ekioba", "platform", "mission", "who runs"],
        "EKIOBA is a cultural e-commerce marketplace celebrating the art, heritage, and traditions of the Benin Kingdom (Edo State, Nigeria). We connect artisans and culture-bearers with buyers worldwide — powered by IDIA Coin blockchain payments, with services spanning hospitality, logistics, and Edo language education.",
    ),
    (
        ["product", "shop", "store", "buy", "sell", "item", "bronze", "coral", "mask", "ivory", "plaque", "bead", "catalog", "collection", "art"],
        "EKIOBA's store features handcrafted Benin Kingdom treasures: gold-plated bronze heads, Idia ivory mask pendants, royal coral bead necklaces, vintage bronze plaques, Benin bronze castings, and royal fashion attire. Each item carries authentic cultural provenance. Browse the Store on the homepage — click any product to add it to your cart.",
    ),
    (
        ["cart", "add to cart", "basket", "order", "purchase", "buy now", "checkout cart"],
        "To shop on EKIOBA: browse the Store section and add items to cart. The basket icon at the top-right shows your live item count and sits just below Connect Wallet. Open it to review items, then checkout with IDIA Coin.",
    ),
    (
        ["pay", "payment", "price", "naira", "idia", "idia coin", "checkout", "cost", "currency", "ngn"],
        "EKIOBA uses IDIA Coin as the native and only checkout currency. Prices are shown in NGN for reference and converted to IDIA at checkout. Connect Tonkeeper (or any TON Connect wallet) from the Connect Wallet action, then complete payment with IDIA Coin.",
    ),
    (
        ["idia coin", "what is idia", "idia token", "idia blockchain", "idia usdt", "idia rate"],
        "IDIA Coin is EKIOBA's native cultural token, honouring Queen Idia — the first Queen Mother of the Benin Kingdom. It runs on the TON network as a Jetton. 1 IDIA ≈ 30 NGN / ~0.018 USDT at current rates. You can earn IDIA by completing Edo Language Academy quizzes and spending it on any EKIOBA product.",
    ),
    (
        ["ton", "ton connect", "tonconnect", "toncoin", "ton wallet", "tonkeeper", "mytonwallet"],
        "Tonkeeper connection is available from the Connect Wallet action in the payment modal. After your wallet connects, IDIA checkout routes through your connected wallet automatically.",
    ),
    (
        ["wallet", "dashboard", "balance", "forecast", "chart", "home page", "home dashboard"],
        "The EKIOBA homepage is your all-in-one dashboard — live product listings, market forecast charts (stocks, crypto, sentiment score), TON wallet status, and your shopping cart. Use the fixed top navigation to jump to Store, Hotels, Cargo, Academy, or Iyobo AI at any time.",
    ),
    (
        ["edo", "benin", "benin kingdom", "benin history", "kingdom", "bini", "edo state", "edo people"],
        "The Benin Kingdom (Edo Kingdom) is one of Africa's oldest and most powerful monarchies, founded ~900 AD in present-day Edo State, Nigeria. It reached its golden age under Oba Ewuare the Great (~1440–1473 AD). The kingdom is world-famous for its extraordinary bronze castings, ivory carvings, oral traditions, and the Oba divine kingship system still active today.",
    ),
    (
        ["oba", "oba of benin", "ewuare", "ovonramwen", "erediauwa", "eweka", "ozolua", "esigie", "ewuare ii"],
        "Notable Obas of Benin: Ewuare I (the Great) unified and expanded the kingdom ~1440 AD; Ozolua the Conqueror (1483–1504) extended the empire through military campaigns; Esigie (1504–1550) established the Iyoba (Queen Mother) title; Ovonramwen Nogbaisi reigned until the 1897 British Punitive Expedition. Ewuare II was crowned in 2016 and is the current Oba.",
    ),
    (
        ["queen idia", "idia queen", "queen mother", "iyoba", "idia mask", "idia pendant", "idia coin history"],
        "Queen Idia was the first Iyoba (Queen Mother) of Benin, mother of Oba Esigie (~1504 AD). She led warriors in battle to defend the kingdom and is celebrated as a symbol of female power and royal courage. The Idia Ivory Mask is a masterpiece of Benin art — held partly in the British Museum — and inspired EKIOBA's IDIA Coin and our Idia Ivory Mask Pendant product.",
    ),
    (
        ["bronze", "bronze casting", "bronze head", "benin bronze", "brass", "casting", "lost wax", "igun"],
        "Benin bronze casting dates to the 13th century, mastered by the hereditary Igun Eronmwon guild using the lost-wax (cire perdue) technique. Artists created commemorative heads of Obas and Iyobas, courtly plaques, and ritual objects of extraordinary artistry. Many bronzes were seized in the 1897 British Punitive Expedition — their repatriation remains an ongoing global conversation. EKIOBA's bronze replicas honour this living tradition.",
    ),
    (
        ["igue festival", "igue", "ugie", "ugie erha oba", "festival", "ceremony", "benin celebration", "royal festival"],
        "The Igue Festival is the most sacred annual ceremony of the Benin Kingdom, held each December. The Oba performs royal renewal rites, honours royal ancestors, and reinforces his divine powers. The Ugie Erha Oba ceremony specifically honours the spirit of the Oba's father. Both festivals feature elaborate royal regalia, court dances, music, and religious offerings.",
    ),
    (
        ["coral", "coral bead", "ivie", "bead jewelry", "royal coral", "coral necklace"],
        "Coral beads (Ivie in Edo) are sacred symbols of royalty and spiritual protection in the Benin Kingdom. Only the Oba, chiefs, and senior title holders may wear specific coral configurations — wearing them without rank is a punishable cultural offence. Red coral was historically imported from the Mediterranean. EKIOBA's Royal Coral Bead Necklace is crafted in authentic Benin style.",
    ),
    (
        ["academy", "learn edo", "edo language", "language academy", "lesson", "quiz", "translate", "vocabulary", "study"],
        "The Edo Language Academy lets you learn the Edo (Bini) language interactively. Features: live Edo↔English translator, 50-question vocabulary quiz with IDIA point rewards, a vocabulary browser by category (greetings, numbers, food, family, nature, culture, body, home), and daily lessons. Visit the Academy via the top navigation bar.",
    ),
    (
        ["edo language greetings", "how to say hello", "good morning edo", "greet in edo", "basic edo"],
        "Basic Edo phrases: 'Koyo' = Hello | 'Otabor' = Good morning | 'Vbe ighe' = Good afternoon | 'Vbe oyi' = Good evening | 'Obo' = Thank you | 'Laro' = Goodbye | 'Ege' = Please | 'Mwen' = I/Me. Edo is a tonal language — pitch changes meaning. Explore all categories in the Edo Language Academy.",
    ),
    (
        ["number", "count", "edo numbers", "how to count", "counting in edo"],
        "Counting in Edo: Ovbokhan (1), Eva (2), Eha (3), Ene (4), Isen (5), Eissen (6), Ihien (7), Eren (8), Ehen (9), Igbe (10), Igbe ne eva (20), Igbe ne eha (30), Iguegbe (100). Practise numbers and more in the Edo Language Academy quiz on EKIOBA.",
    ),
    (
        ["hotel", "accommodation", "stay", "lodging", "book hotel", "benin city hotel", "lagos hotel", "abuja hotel", "port harcourt hotel"],
        "EKIOBA lists prestigious hotels across 4 Nigerian cities: Benin City (Protea Hotel Emotan, Oti Hotels, Avbiama Hotel); Abuja (Transcorp Hilton, Sheraton Abuja, Bolton White); Lagos (Eko Hotel & Suites, Lagos Marriott Ikeja, Federal Palace Hotel); Port Harcourt (Novotel PH, Hawthorn Suites, Presidential Hotel PH). Visit the Hotels page for full listings and booking details.",
    ),
    (
        ["cargo", "shipping", "ship", "freight", "logistics", "courier", "deliver package", "send goods"],
        "EKIOBA Cargo offers reliable shipping across Nigeria and internationally. Get an instant quote online (enter distance and weight), book a pickup, and track your shipment in real time via SSE stream. We use tamper-evident packaging, milestone scan checkpoints, insurance on high-value cargo, and SLA-bound delivery windows. Visit the Cargo page to get a quote.",
    ),
    (
        ["deliver", "where do you ship", "international shipping", "worldwide", "abroad", "send abroad"],
        "We deliver within Nigeria (Benin City, Lagos, Abuja, Port Harcourt, and all states) and internationally. International orders use partner couriers with full customs documentation. For high-value artworks and cultural items, contact support for a custom international shipping quote.",
    ),
    (
        ["forecast", "market", "stock market", "crypto market", "bitcoin", "ethereum", "price prediction", "sentiment"],
        "The EKIOBA forecast dashboard aggregates live market data from Yahoo Finance, Google Finance, and SoSoValue. It tracks crypto price trends, stock index movements, and a Fear & Greed sentiment index. Find it on the homepage — scroll to the Forecast section or visit /api/dashboard/forecast for raw JSON data.",
    ),
    (
        ["return", "refund", "exchange", "policy", "dispute", "cancel order"],
        "Returns are accepted within 14 days of delivery for items in original, undamaged condition with original packaging. Blockchain (IDIA Coin) payments are non-reversible once confirmed on-chain per blockchain protocol. For disputes, contact EKIOBA support with your order ID and photo evidence of condition. We mediate all cases fairly.",
    ),
    (
        ["contact", "support", "help", "email", "customer service", "reach ekioba", "phone number"],
        "EKIOBA support is available via the contact form on the homepage. Reference your order ID for faster resolution. Our team handles product inquiries, payment issues (include your blockchain tx hash), shipping updates, and Edo cultural questions. Business-day response time is typically within 24 hours.",
    ),
]


async def _ddg_search(query: str) -> str | None:
    """DuckDuckGo Instant Answer lookup — no API key required. Returns a brief snippet or None."""
    try:
        async with httpx.AsyncClient(timeout=6.0, follow_redirects=True) as client:
            r = await client.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"},
                headers={"User-Agent": "EKIOBA-Iyobo/1.0"},
            )
            d = r.json()
        abstract = (d.get("AbstractText") or "").strip()
        if abstract:
            source = d.get("AbstractSource") or ""
            return abstract[:420] + (f" — via {source}" if source else "")
        for topic in d.get("RelatedTopics") or []:
            if isinstance(topic, dict) and topic.get("Text"):
                return str(topic["Text"])[:320]
    except Exception:
        pass
    return None


def _iyobo_local_reply(text: str) -> str:
    lower = text.lower()
    for keywords, reply in _IYOBO_KNOWLEDGE:
        if any(kw in lower for kw in keywords):
            return reply
    return (
        "I'm Iyobo, EKIOBA's cultural guide. I can help with products, payments, "
        "the Benin Kingdom heritage, shipping, or the home dashboard. What would you like to know?"
    )


@app.post("/api/chat/proxy", response_class=HTMLResponse)
async def chat_proxy(message: str = Form(default="")) -> HTMLResponse:
    text = message.strip()
    if not text:
        return HTMLResponse('<div class="chat-bubble bot">Ask Iyobo anything about EKIOBA.</div>')

    search_results = await _extract_link_search_results(text)
    web_answer = await _ddg_search(text)

    # Try external AI service: NEXT_PUBLIC_IYOBO_API_URL takes precedence, then AI_ASSISTANT_URL
    backend_url = _resolve_chat_url()
    if backend_url and "localhost" not in backend_url:
        async with httpx.AsyncClient(timeout=20.0) as client:
            try:
                payload: dict[str, Any] = {"message": text}
                context: dict[str, Any] = {}
                if search_results:
                    context["search_results"] = search_results
                if web_answer:
                    context["web_lookup"] = web_answer
                if context:
                    payload["context"] = context
                response = await client.post(
                    backend_url,
                    json=payload,
                    headers=_build_ai_headers(),
                )
                response.raise_for_status()
                data = response.json()
                reply = data.get("reply") or data.get("response") or data.get("answer") or ""
                if reply:
                    return HTMLResponse(f'<div class="chat-bubble bot">{reply}</div>')
            except Exception:
                pass  # Fall through to local knowledge base

    lower = text.lower()
    if any(k in lower for k in ["forecast", "market", "price", "bitcoin", "stock", "crypto"]):
        forecast = await _safe_dashboard_forecast()
        stocks = forecast.get("stocks", {}).get("predicted", [])
        crypto = forecast.get("crypto", {}).get("predicted", [])
        sentiment = forecast.get("sentiment", {}).get("values", [50])
        stock_tip = stocks[-1] if stocks else "N/A"
        crypto_tip = crypto[-1] if crypto else "N/A"
        sent_tip = sentiment[0] if sentiment else "N/A"
        reply = (
            f"Live market snapshot: next stock estimate {stock_tip}, next crypto estimate {crypto_tip}, "
            f"sentiment score {sent_tip}. Sources: Yahoo Finance, Google Finance, SoSoValue, and exchange feeds."
        )
    else:
        reply = _iyobo_local_reply(text)
        _generic_fallback = "I'm Iyobo, EKIOBA's cultural guide" in reply
        _question_like = any(
            token in lower
            for token in [
                "what", "who", "when", "where", "why", "how",
                "latest", "current", "history", "price", "news",
                "tell me", "explain", "describe",
            ]
        )
        if web_answer and (_generic_fallback or _question_like):
            reply = f"{reply}\n\nWeb lookup: {web_answer}"
    return HTMLResponse(f'<div class="chat-bubble bot">{reply}</div>')


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


# ── Hotels page ────────────────────────────────────────────────────────────

@app.get("/hotels", response_class=HTMLResponse)
async def hotels_page(request: Request) -> HTMLResponse:
    listings: list[dict[str, Any]] = []
    service_offline = False
    base = (HOTELS_SERVICE_URL or "").strip().rstrip("/")
    if base:
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                r = await client.get(f"{base}/api/listings/", headers={"Accept": "application/json"})
                r.raise_for_status()
                data = r.json()
                if isinstance(data, list):
                    listings = data
        except Exception:
            service_offline = True
    else:
        service_offline = True

    if not listings:
        listings = PRESTIGIOUS_HOTELS

    return templates.TemplateResponse("hotels.html", {
        "request": request,
        "listings": listings,
        "service_offline": service_offline,
    })


# ── Cargo page ─────────────────────────────────────────────────────────────

@app.get("/cargo", response_class=HTMLResponse)
async def cargo_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("cargo.html", {"request": request})


@app.post("/api/cargo/quote")
async def cargo_quote(request: Request) -> JSONResponse:
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON."}, status_code=400)

    base = (CARGO_SERVICE_URL or "").strip().rstrip("/")
    if base:
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                r = await client.post(f"{base}/quote", json=payload, headers={"Accept": "application/json"})
                r.raise_for_status()
                return JSONResponse(r.json())
            except Exception:
                pass

    # Local fallback calculation based on good shipping-practice components:
    # linehaul + weight + handling + insurance reserve.
    try:
        distance = float(payload.get("distance_km", 0))
        weight = float(payload.get("weight_kg", 0))
        if distance <= 0 or weight <= 0:
            return JSONResponse({"error": "Distance and weight must be positive."}, status_code=422)
        handling_fee = 2500
        linehaul = distance * 120
        weight_fee = weight * 450
        insurance_fee = max(1000, 0.02 * (linehaul + weight_fee))
        cost = round(handling_fee + linehaul + weight_fee + insurance_fee, 2)
        return JSONResponse({
            "estimated_cost": cost,
            "breakdown": {
                "handling_fee": handling_fee,
                "linehaul_fee": round(linehaul, 2),
                "weight_fee": round(weight_fee, 2),
                "insurance_fee": round(insurance_fee, 2),
            },
            "best_practice": "Insure high-value cargo, verify packaging integrity, and track via live scan checkpoints.",
        })
    except (TypeError, ValueError):
        return JSONResponse({"error": "Invalid values."}, status_code=422)


@app.get("/api/cargo/best-practices")
async def cargo_best_practices() -> JSONResponse:
    return JSONResponse(
        {
            "standards": [
                "Use tamper-evident packaging for high-value items.",
                "Capture pickup and delivery proof-of-condition photos.",
                "Provide milestone scans: pickup, hub, out-for-delivery, delivered.",
                "Apply SLA windows by route class and notify on ETA drift.",
                "Insure shipments above risk threshold and disclose claim process.",
            ]
        }
    )



@app.get("/api/cargo/track/{shipment_id}")
async def cargo_track(shipment_id: str) -> JSONResponse:
    base = (CARGO_SERVICE_URL or "").strip().rstrip("/")
    if base:
        async with httpx.AsyncClient(timeout=8.0) as client:
            try:
                r = await client.get(
                    f"{base}/shipments/{shipment_id}",
                    headers={"Accept": "application/json"},
                )
                r.raise_for_status()
                return JSONResponse(r.json())
            except Exception:
                pass
    return JSONResponse({"shipment_id": shipment_id, "status": "in_transit", "eta_hours": 6})


@app.get("/api/cargo/track/{shipment_id}/stream")
async def cargo_track_stream(shipment_id: str):
    """Server-Sent Events stream for real-time shipment tracking updates."""
    import asyncio

    async def event_generator():
        statuses = ["order_placed", "picked_up", "in_transit", "at_hub", "out_for_delivery", "delivered"]
        base = (CARGO_SERVICE_URL or "").strip().rstrip("/")

        for i in range(30):  # Stream for up to ~60 seconds
            data: dict[str, Any] = {"shipment_id": shipment_id, "status": "in_transit", "eta_hours": max(1, 6 - i)}

            if base:
                try:
                    async with httpx.AsyncClient(timeout=4.0) as client:
                        r = await client.get(f"{base}/shipments/{shipment_id}", headers={"Accept": "application/json"})
                        r.raise_for_status()
                        data = r.json()
                except Exception:
                    pass

            payload = json.dumps(data)
            yield f"data: {payload}\n\n"

            if data.get("status") == "delivered":
                break
            await asyncio.sleep(2)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/cargo/book")
async def cargo_book(request: Request) -> JSONResponse:
    """Book a cargo shipment and receive a shipment ID."""
    import uuid as _uuid
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON."}, status_code=400)

    base = (CARGO_SERVICE_URL or "").strip().rstrip("/")
    if base:
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                r = await client.post(f"{base}/book", json=payload, headers={"Accept": "application/json"})
                r.raise_for_status()
                return JSONResponse(r.json())
            except Exception:
                pass

    # Fallback: generate a booking reference
    shipment_id = f"SHP-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{str(_uuid.uuid4())[:6].upper()}"
    return JSONResponse({
        "shipment_id": shipment_id,
        "status": "order_placed",
        "eta_hours": 24,
        "message": "Your shipment has been booked. Track it using the shipment ID.",
    })


# ── Language Academy page ──────────────────────────────────────────────────

@app.get("/academy", response_class=HTMLResponse)
async def academy_page(request: Request) -> HTMLResponse:
    service_offline = False
    base = (LANGUAGE_ACADEMY_URL or "").strip().rstrip("/")
    if base:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"{base}/health", headers={"Accept": "application/json"})
                if r.status_code >= 400:
                    service_offline = True
        except Exception:
            service_offline = True
    else:
        service_offline = True
    return templates.TemplateResponse("academy.html", {"request": request, "service_offline": service_offline})


@app.post("/api/academy/translate")
async def academy_translate(request: Request) -> JSONResponse:
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON."}, status_code=400)

    base = (LANGUAGE_ACADEMY_URL or "").strip().rstrip("/")
    if base:
        async with httpx.AsyncClient(timeout=12.0) as client:
            try:
                r = await client.post(
                    f"{base}/translate",
                    json=payload,
                    headers={"Accept": "application/json"},
                )
                r.raise_for_status()
                return JSONResponse(r.json())
            except Exception:
                pass
    return JSONResponse({"error": "Translation service unavailable."}, status_code=503)


@app.get("/api/academy/vocabulary")
async def academy_vocabulary(limit: int = 20, search: str = "") -> JSONResponse:
    base = (LANGUAGE_ACADEMY_URL or "").strip().rstrip("/")
    if base:
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                params: dict[str, Any] = {"limit": limit}
                if search:
                    params["q"] = search
                r = await client.get(
                    f"{base}/vocabulary",
                    params=params,
                    headers={"Accept": "application/json"},
                )
                r.raise_for_status()
                return JSONResponse(r.json())
            except Exception:
                pass
    items = _academy_vocab_filtered(search=search)[: max(1, min(limit, 100))]
    return JSONResponse({"items": items, "fallback": True})


@app.get("/api/academy/quiz/question")
async def academy_quiz_question() -> JSONResponse:
    base = (LANGUAGE_ACADEMY_URL or "").strip().rstrip("/")
    if base:
        async with httpx.AsyncClient(timeout=8.0) as client:
            try:
                r = await client.get(f"{base}/quiz/question", headers={"Accept": "application/json"})
                r.raise_for_status()
                return JSONResponse(r.json())
            except Exception:
                pass
    return JSONResponse({"error": "Quiz service unavailable."}, status_code=503)


@app.get("/api/academy/quiz/section")
async def academy_quiz_section(size: int = 50, category: str = "") -> JSONResponse:
    base = (LANGUAGE_ACADEMY_URL or "").strip().rstrip("/")
    if base:
        async with httpx.AsyncClient(timeout=12.0) as client:
            try:
                params: dict[str, Any] = {"size": size}
                if category:
                    params["category"] = category
                r = await client.get(
                    f"{base}/quiz/section",
                    params=params,
                    headers={"Accept": "application/json"},
                )
                r.raise_for_status()
                return JSONResponse(r.json())
            except Exception:
                pass
    return JSONResponse({"questions": _build_quiz_section(size=size, category=category), "fallback": True})


@app.post("/api/academy/quiz/answer")
async def academy_quiz_answer(request: Request) -> JSONResponse:
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON."}, status_code=400)

    base = (LANGUAGE_ACADEMY_URL or "").strip().rstrip("/")
    if base:
        async with httpx.AsyncClient(timeout=8.0) as client:
            try:
                r = await client.post(
                    f"{base}/quiz/answer",
                    json=payload,
                    headers={"Accept": "application/json"},
                )
                r.raise_for_status()
                data = r.json()
                # Normalise field names: backend uses awarded_tokens, template expects points_awarded
                if "awarded_tokens" in data and "points_awarded" not in data:
                    data["points_awarded"] = data["awarded_tokens"]
                return JSONResponse(data)
            except Exception:
                pass
    answer = str(payload.get("answer", "")).strip().lower()
    expected = str(payload.get("expected", "")).strip().lower()
    is_correct = bool(answer and expected and answer == expected)
    points_awarded = 10 if is_correct else 0
    return JSONResponse(
        {
            "correct": is_correct,
            "expected": payload.get("expected", ""),
            "points_awarded": points_awarded,
            "awarded_tokens": points_awarded,
            "message": "Correct answer." if is_correct else "Incorrect answer.",
            "fallback": True,
        }
    )


@app.post("/api/academy/quiz/complete")
async def academy_quiz_complete(request: Request) -> JSONResponse:
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON."}, status_code=400)

    answered = int(payload.get("answered", 0) or 0)
    correct = int(payload.get("correct", 0) or 0)
    base_points = max(0, correct) * 10
    completion_bonus = 100 if answered >= 50 else 0
    total_award = base_points + completion_bonus
    return JSONResponse(
        {
            "answered": answered,
            "correct": correct,
            "base_points": base_points,
            "completion_bonus": completion_bonus,
            "total_award": total_award,
            "message": "Quiz completed. Completion bonus awarded." if completion_bonus else "Quiz progress saved.",
        }
    )


@app.get("/api/academy/lesson/daily")
async def academy_daily_lesson(size: int = 5, category: str = "") -> JSONResponse:
    base = (LANGUAGE_ACADEMY_URL or "").strip().rstrip("/")
    if base:
        async with httpx.AsyncClient(timeout=8.0) as client:
            try:
                params: dict[str, Any] = {"size": size}
                if category:
                    params["category"] = category
                r = await client.get(f"{base}/lesson/daily", params=params, headers={"Accept": "application/json"})
                r.raise_for_status()
                return JSONResponse(r.json())
            except Exception:
                pass
    items = _academy_vocab_filtered(category=category)
    random.shuffle(items)
    return JSONResponse(
        {
            "title": "Daily Edo Lesson",
            "items": items[: max(1, min(size, 20))],
            "fallback": True,
        }
    )


@app.post("/api/academy/lesson/create")
async def academy_create_lesson(request: Request) -> JSONResponse:
    """Create a custom lesson. Proxies to language academy service."""
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON."}, status_code=400)

    base = (LANGUAGE_ACADEMY_URL or "").strip().rstrip("/")
    if base:
        async with httpx.AsyncClient(timeout=12.0) as client:
            try:
                r = await client.post(
                    f"{base}/lesson/create",
                    json=payload,
                    headers={"Accept": "application/json"},
                )
                r.raise_for_status()
                return JSONResponse(r.json())
            except Exception:
                pass

    # Fallback: build a lesson from vocabulary
    title = str(payload.get("title", "Custom Lesson"))
    category = payload.get("category")
    size = int(payload.get("size", 5))
    lesson_id = f"lesson-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    return JSONResponse({
        "lesson_id": lesson_id,
        "title": title,
        "category": category,
        "size": size,
        "status": "created",
        "message": "Lesson created. Connect the language academy service for full content.",
    })


@app.get("/api/academy/quiz/points/{user_id}")
async def academy_quiz_points(user_id: str) -> JSONResponse:
    base = (LANGUAGE_ACADEMY_URL or "").strip().rstrip("/")
    if base:
        async with httpx.AsyncClient(timeout=8.0) as client:
            try:
                r = await client.get(f"{base}/quiz/points/{user_id}", headers={"Accept": "application/json"})
                r.raise_for_status()
                return JSONResponse(r.json())
            except Exception:
                pass
    return JSONResponse({"user_id": user_id, "token_balance": 0})


# ── Hotels booking ─────────────────────────────────────────────────────────

@app.post("/api/hotels/book")
async def hotels_book(request: Request) -> JSONResponse:
    """Book a hotel room. Supports idia coin payment."""
    import uuid as _uuid
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON."}, status_code=400)

    base = (HOTELS_SERVICE_URL or "").strip().rstrip("/")
    if base:
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                r = await client.post(f"{base}/api/book/", json=payload, headers={"Accept": "application/json"})
                r.raise_for_status()
                return JSONResponse(r.json())
            except Exception:
                pass

    # Generate a booking reference
    booking_ref = f"BK-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{str(_uuid.uuid4())[:6].upper()}"
    price_ngn = float(payload.get("price_per_night", 0)) * int(payload.get("nights", 1))
    chain = payload.get("chain", "")

    response_data: dict[str, Any] = {
        "booking_ref": booking_ref,
        "hotel": payload.get("hotel_title", "Selected Hotel"),
        "city": payload.get("city", ""),
        "check_in": payload.get("check_in", ""),
        "check_out": payload.get("check_out", ""),
        "nights": payload.get("nights", 1),
        "total_ngn": price_ngn,
        "status": "pending_payment",
    }

    if chain == "ton" and price_ngn > 0:
        try:
            create_ton_payment_request = _get_payment_handlers()
            product_name = f"Hotel: {payload.get('hotel_title', 'Room')}"
            response_data["payment"] = await create_ton_payment_request(
                price_ngn,
                product_name,
                booking_ref,
                sender_address=payload.get("sender_address"),
            )
        except (ValueError, TonServiceError) as exc:
            # The booking still stands; say why payment could not be prepared
            # rather than returning a booking with no payment and no reason.
            response_data["payment_error"] = str(exc)
        except Exception:
            response_data["payment_error"] = "Could not prepare the IDIA payment. Please retry."

    return JSONResponse(response_data)


@app.get("/api/hotels/listings")
async def hotels_listings_api(city: str = "", limit: int = 20) -> JSONResponse:
    """API endpoint to fetch hotel listings with optional city filter."""
    base = (HOTELS_SERVICE_URL or "").strip().rstrip("/")
    if base:
        async with httpx.AsyncClient(timeout=8.0) as client:
            try:
                params: dict[str, Any] = {"limit": limit}
                if city:
                    params["city"] = city
                r = await client.get(f"{base}/api/listings/", params=params, headers={"Accept": "application/json"})
                r.raise_for_status()
                data = r.json()
                return JSONResponse({"listings": data if isinstance(data, list) else [], "count": len(data) if isinstance(data, list) else 0})
            except Exception:
                pass

    filtered = [h for h in PRESTIGIOUS_HOTELS if not city or city.lower() in h["city"].lower()]
    filtered = filtered[: max(1, min(limit, 100))]
    return JSONResponse({"listings": filtered, "count": len(filtered), "fallback": True})


@app.get("/{filename}")
async def public_root_files(filename: str):
    # Keep existing root-level public assets (manifest, token metadata) compatible.
    candidate = PUBLIC_DIR / filename
    if candidate.exists() and candidate.is_file():
        return FileResponse(candidate)
    return JSONResponse({"error": "Not found"}, status_code=404)
