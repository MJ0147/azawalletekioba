import logging
import os
import re
import sys
from datetime import datetime, timezone
from typing import Optional, Dict, Any

import httpx
from fastapi import FastAPI, Depends, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn
from sqlalchemy.orm import Session
from sqlalchemy import text
from deps import get_db
from config import settings

# Setup structured logging for Cloud Run
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("iyobo-service")

TELEGRAM_TOKEN = settings.TELEGRAM_BOT_TOKEN or os.environ.get("TELEGRAM_BOT_TOKEN")
COPILOT_API_KEY = settings.COPILOT_API_KEY
COPILOT_BASE_URL = settings.COPILOT_BASE_URL.rstrip("/")
COPILOT_MODEL = settings.COPILOT_MODEL

IYOBO_SYSTEM_PROMPT = """
You are Iyobo — the intelligent, culturally-grounded AI assistant of EKIOBA, the premier Edo Kingdom
cultural marketplace and Web3 commerce platform.

## Identity & Tone
- Warm, knowledgeable, and precise. You blend Edo royal hospitality with expert-level accuracy.
- Address users respectfully; occasionally use real Edo greetings such as "Koyo" (hello/hi),
  "Obowie" (good morning/greetings), or "Vhe o ye rie?" (how are you?) to set a cultural tone,
  but never overdo it.
- You NEVER fabricate facts. If you are uncertain, say so and offer to research further.

## EKIOBA Platform Knowledge
- EKIOBA sells authentic Edo Kingdom artifacts, fashion, jewelry, bronze works, food, and cultural items.
- Payment is processed with **Idia Coin (IDIA)** — EKIOBA's native Web3 token, a Jetton on the
  **TON** blockchain. TON is the only chain EKIOBA settles on.
  - Merchant receives IDIA Jettons on the TON chain; transfers are verified via the TON API.
  - Conversion: NGN → IDIA via live CoinGecko rate (fallback: 1 IDIA ≈ ₦30, ~0.02 USD).
- Cart checkout aggregates all items into a single blockchain payment (one transaction for the whole
  cart total, not per-item).
- Users connect wallets via **TON Connect 2** — Tonkeeper, MyTonWallet, Telegram Wallet and any
  other TON Connect compatible wallet.

## Edo Academy (Language & Culture)
- EKIOBA hosts an **Edo Language Academy** with structured lesson packs covering greetings,
  numbers, family terms, market vocabulary, royal court phrases, proverbs, and song lyrics.
- After each lesson set, users take a **50-question randomised quiz**. Correct answers award
  **Aza Points** redeemable in the store.
- Sample Edo vocabulary you know:
  - Ẹ káàbọ̀ = Welcome | Ọ dẹ = Goodbye | Ima = I/Me | Ọ se = Thank you
  - Ẹvbo = Town/Village | Ọba = King | Iye = Mother | Ọse = Fish
  - Ígho = Money | Ọghẹn = God | Ẹmwi = Thing | Vhe o ye rie? = How are you?

## Forecast & Market Intelligence
- You can discuss crypto/stock/market forecasts using live data sourced from SoSoValue, Yahoo Finance,
  and Google Finance search snippets.
- Provide nuanced, caveated analysis: distinguish trend signals from predictions, cite sources, and
  always remind users that this is not financial advice.

## Cargo & Shipping
- EKIOBA's cargo service uses best-in-class Nigerian logistics partners (GIG Logistics, Kobo360,
  DHL Nigeria, NIPOST) plus international options (DHL Express, FedEx).
- Key practices: real-time tracking, insurance for high-value Edo artifacts, cold-chain option for
  food items, last-mile delivery to Benin City, Lagos, Abuja, and Port Harcourt.

## Hotels
- EKIOBA partners with prestigious hotels in Benin City (Protea Emotan, Oti Hotels),
  Abuja (Transcorp Hilton, Sheraton Abuja), Lagos (Eko Hotel & Suites, The George, Radisson Blu),
  and Port Harcourt (Marriott Port Harcourt, Presidential Hotel).
- You can assist with room enquiries, price ranges, and booking guidance.

## Behavioural Rules
1. When search/context results are provided, USE them and CITE the source (name + URL).
2. When no context is provided, reason from your embedded knowledge above.
3. Keep replies concise unless the user asks for detail.
4. Never generate or guess wallet private keys, seed phrases, or security credentials.
5. If asked about competitor platforms, stay neutral and redirect to EKIOBA's unique value.
6. Always speak in the user's language; default to English if uncertain.
"""

app = FastAPI(title="Iyobo AI Assistant", description="AI Service for Ekioba E-commerce")

# Allow CORS for frontend interaction
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="The user's input message")
    user_id: Optional[str] = Field(None, description="Optional user ID for context")
    context: Optional[Dict] = Field(None, description="Additional context (e.g., cart items)")


class ChatResponse(BaseModel):
    reply: str
    intent: Optional[str] = None


class UIGenerationRequest(BaseModel):
    component_type: str = Field(..., description="Type of UI component to generate (header, footer, navigation)")
    theme: Optional[str] = Field("modern", description="UI theme/style (modern, minimal, corporate, etc.)")
    features: Optional[list[str]] = Field([], description="Specific features to include")
    brand_name: Optional[str] = Field("Ekioba", description="Brand/company name")
    description: Optional[str] = Field(None, description="Additional context or requirements")


async def copilot_chat_completion(
    messages: list[dict[str, str]],
    model: str,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
) -> str:
    """Call a Copilot-compatible chat completions endpoint and return message text."""
    if not COPILOT_API_KEY:
        raise RuntimeError("Missing COPILOT_API_KEY")

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
    }
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    if temperature is not None:
        payload["temperature"] = temperature

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{COPILOT_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {COPILOT_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

async def get_ai_response(message: str, raise_on_error: bool = False) -> str:
    """Centralized method to get real-time AI responses."""
    try:
        return await copilot_chat_completion(
            messages=[
                {"role": "system", "content": IYOBO_SYSTEM_PROMPT},
                {"role": "user", "content": message}
            ],
            model=COPILOT_MODEL,
        )
    except Exception as e:
        logger.error(f"AI Service Error: {e}")
        if raise_on_error:
            raise e
        return "I'm having trouble connecting to my brain right now. Please try again later."


async def generate_ai_response(user_message: str, search_results: list[dict[str, Any]]) -> str:
    """Generate a richer response using top external/context results and explicit source citation guidance."""
    context_snippets: list[str] = []
    for result in search_results[:5]:
        name = str(result.get("name") or "Unknown source")
        snippet = str(result.get("snippet") or "")
        url = str(result.get("url") or "N/A")
        context_snippets.append(f"- {name}: {snippet} (Source: {url})")

    context_text = "\n".join(context_snippets) if context_snippets else "No external search results provided."

    system_prompt = (
        f"{IYOBO_SYSTEM_PROMPT}\n\n"
        "## Live Search Context (USE these results when answering — cite source name and URL):\n"
        f"{context_text}\n\n"
        "Instructions: Synthesise the search results above with your embedded knowledge. "
        "Quote or paraphrase relevant snippets, always citing '(Source: <name>, <url>)'. "
        "If results contradict each other, note the discrepancy and recommend the most authoritative source. "
        "If results are insufficient, say so clearly and offer a follow-up question."
    )

    return await copilot_chat_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        model=COPILOT_MODEL,
    )


def _extract_related_topics(items: list[dict[str, Any]], output: list[dict[str, Any]], limit: int) -> None:
    for item in items:
        if len(output) >= limit:
            return
        if isinstance(item, dict) and "Topics" in item and isinstance(item["Topics"], list):
            _extract_related_topics(item["Topics"], output, limit)
            continue
        if not isinstance(item, dict):
            continue
        text = str(item.get("Text") or "").strip()
        url = str(item.get("FirstURL") or "").strip()
        if not text:
            continue
        name = text.split(" - ", 1)[0][:80] or "Web result"
        output.append({"name": name, "snippet": text, "url": url or "N/A"})


async def _auto_web_search_results(query: str, limit: int = 5) -> list[dict[str, Any]]:
    clean_query = re.sub(r"\s+", " ", (query or "")).strip()
    if len(clean_query) < 3:
        return []

    params = {
        "q": clean_query,
        "format": "json",
        "no_redirect": "1",
        "no_html": "1",
        "skip_disambig": "1",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("https://api.duckduckgo.com/", params=params)
            response.raise_for_status()
            payload = response.json()
    except Exception as e:
        logger.warning(f"Auto web search failed: {e}")
        return []

    results: list[dict[str, Any]] = []
    abstract = str(payload.get("AbstractText") or "").strip()
    abstract_url = str(payload.get("AbstractURL") or "").strip()
    heading = str(payload.get("Heading") or "DuckDuckGo").strip() or "DuckDuckGo"
    if abstract:
        results.append(
            {
                "name": heading,
                "snippet": abstract,
                "url": abstract_url or "https://duckduckgo.com/?q=" + clean_query.replace(" ", "+"),
            }
        )

    related_topics = payload.get("RelatedTopics")
    if isinstance(related_topics, list):
        _extract_related_topics(related_topics, results, limit)

    return results[:limit]

@app.get("/", tags=["Health"])
def root():
    """Root endpoint for basic connectivity check."""
    return {"service": "Iyobo AI Assistant", "status": "running"}


@app.get("/ready", tags=["Health"])
def readiness_check():
    """Readiness endpoint that does not require database access."""
    return {"status": "ready"}


@app.get("/health", tags=["Health"])
def health_check(db: Session = Depends(get_db)):
    """Health check for database connectivity and service status."""
    try:
        # Execute a simple query to verify the MySQL connection
        db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed"
        )


@app.post("/telegram/webhook", tags=["Telegram"])
async def telegram_webhook(request: Request):
    """
    Webhook to receive messages from Telegram.
    Wakes up Cloud Run on demand.
    """
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not configured")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Telegram configuration missing")

    data = await request.json()
    
    # Basic echo/reply logic
    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        user_text = data["message"].get("text", "")
        logger.info(f"Telegram message from {chat_id}: {user_text}")

        # Get real-time AI response
        ai_reply = await get_ai_response(user_text)

        # Send reply back to Telegram
        async with httpx.AsyncClient() as client:
            await client.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={"chat_id": chat_id, "text": ai_reply}
            )

    return {"status": "ok"}

@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(payload: ChatRequest):
    """Process a chat message with real-time AI."""
    logger.info(f"Received message from user {payload.user_id}: {payload.message}")

    try:
        ctx = payload.context if isinstance(payload.context, dict) else {}
        search_results = ctx.get("search_results", []) if isinstance(ctx, dict) else []
        if not isinstance(search_results, list):
            search_results = []

        if not search_results:
            search_results = await _auto_web_search_results(payload.message)

        if isinstance(search_results, list) and search_results:
            reply = await generate_ai_response(payload.message, search_results)
        else:
            reply = await get_ai_response(payload.message, raise_on_error=True)
    except Exception:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="AI Service unreachable")

    return {
        "reply": reply,
        "intent": "dynamic_ai",
    }


async def generate_ui_component(
    component_type: str,
    theme: Optional[str],
    features: Optional[list[str]],
    brand_name: Optional[str],
    description: Optional[str] = None,
) -> str:
    """Generate UI component markup using AI."""
    prompt = f"""Generate {component_type} HTML markup for a {theme} themed website.

Brand: {brand_name}
Features to include: {', '.join(features) if features else 'standard features'}
{description if description else ''}

Requirements:
- Use semantic HTML5
- Include proper accessibility attributes
- Use Tailwind CSS classes for styling
- Make it responsive (mobile-first)
- Include relevant icons (use Lucide icon names)
- Return only the HTML markup, no explanations

Generate clean, modern {component_type} markup:"""

    try:
        return await copilot_chat_completion(
            messages=[
                {"role": "system", "content": "You are a UI/UX expert that generates clean, semantic HTML markup. Focus on accessibility, responsiveness, and modern design patterns."},
                {"role": "user", "content": prompt}
            ],
            model=COPILOT_MODEL,
            max_tokens=2000,
            temperature=0.7
        )
    except Exception as e:
        logger.error(f"UI Generation Error: {e}")
        return f'<div class="error">Failed to generate {component_type}</div>'


@app.post("/generate-ui", tags=["UI Generation"])
async def generate_ui(payload: UIGenerationRequest):
    """Generate UI component markup using AI."""
    logger.info(f"Generating {payload.component_type} with theme: {payload.theme}")

    try:
        markup = await generate_ui_component(
            payload.component_type,
            payload.theme or "modern",
            payload.features or [],
            payload.brand_name or "Ekioba",
            payload.description
        )
    except Exception:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="UI Generation service unreachable")

    return {
        "component_type": payload.component_type,
        "markup": markup,
        "theme": payload.theme,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    # Cloud Run injects the PORT environment variable
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"Starting Iyobo AI Service on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
