import logging
import os
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

IYOBO_SYSTEM_PROMPT = "You are Iyobo, the AI assistant for Ekioba e-commerce. You help users with shopping, orders, and payments via Idia Coin (on TON/Solana). Be helpful, professional, and concise."

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
