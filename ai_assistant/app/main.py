import hmac
import logging
import os
import re
import sys
from datetime import datetime, timezone
from functools import lru_cache
from typing import Optional, Dict, Any

import httpx
from fastapi import FastAPI, Depends, Query, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn
from sqlalchemy.orm import Session
from sqlalchemy import text
from deps import get_db
from config import settings

from app.grok_client import (
    GrokError,
    GrokNotConfigured,
    GrokReply,
    build_payload,
    create_response,
    parse_response,
)
from app.knowledge_base import KnowledgeBase, resolve_root
from app.iyobo_agent import IyoboAgent
from app.stateless_answer import IYOBO_SYSTEM_PROMPT, answer_without_memory, build_instructions, format_reply

# Setup structured logging for Cloud Run
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("iyobo-service")

TELEGRAM_TOKEN = settings.TELEGRAM_BOT_TOKEN or os.environ.get("TELEGRAM_BOT_TOKEN")

AI_UNAVAILABLE_REPLY = "I'm having trouble connecting to my brain right now. Please try again later."

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
    sources: list[str] = Field(default_factory=list, description="Web pages Grok cited")
    knowledge_base_sources: list[str] = Field(
        default_factory=list, description="Knowledge Base files given to Grok as context"
    )


class UIGenerationRequest(BaseModel):
    component_type: str = Field(..., description="Type of UI component to generate (header, footer, navigation)")
    theme: Optional[str] = Field("modern", description="UI theme/style (modern, minimal, corporate, etc.)")
    features: Optional[list[str]] = Field([], description="Specific features to include")
    brand_name: Optional[str] = Field("Ekioba", description="Brand/company name")
    description: Optional[str] = Field(None, description="Additional context or requirements")


@lru_cache(maxsize=1)
def get_knowledge_base() -> KnowledgeBase:
    """Load and index the Knowledge Base once per worker process."""
    return KnowledgeBase.load(
        resolve_root(settings.KNOWLEDGE_BASE_DIR),
        exclude=settings.knowledge_base_exclude_list(),
    )


_WEB_USER_ID = re.compile(r"[A-Za-z0-9_-]{16,64}")


def web_user_id(raw: Optional[str]) -> Optional[str]:
    """The website's visitor id, namespaced so a web request can never pose as a Telegram user.

    Visitor ids are random values the website keeps in a cookie. Anything else is ignored, and the
    message is answered without memory.
    """
    candidate = (raw or "").strip()
    return f"web:{candidate}" if _WEB_USER_ID.fullmatch(candidate) else None


@lru_cache(maxsize=1)
def get_iyobo_agent() -> IyoboAgent:
    """The ADK agent that remembers people and learns from reviewed suggestions (one per worker)."""
    return IyoboAgent(settings=settings, instruction=IYOBO_SYSTEM_PROMPT, knowledge_base=get_knowledge_base)


async def ask_iyobo(
    message: str,
    link_results: Optional[list[dict[str, Any]]] = None,
    user_id: Optional[str] = None,
) -> tuple[GrokReply, list[str]]:
    """Answer a message. People with an id get the learning agent, which remembers them.

    Visitors without an id get a stateless answer, and so does everyone if the memory database
    can't be reached. Returns the reply and the Knowledge Base files given as context.
    """
    if user_id is None:
        return await ask_iyobo_stateless(message, link_results)
    try:
        return await get_iyobo_agent().chat(user_id, message, link_results)
    except GrokError:
        raise
    except Exception as exc:
        # Memory storage being down must not take the assistant down with it.
        logger.error("Learning agent unavailable (%s: %s); answering without memory", exc.__class__.__name__, exc)
        return await ask_iyobo_stateless(message, link_results)


async def ask_iyobo_stateless(
    message: str, link_results: Optional[list[dict[str, Any]]] = None
) -> tuple[GrokReply, list[str]]:
    """Answer without memory: Knowledge Base first, web search to fill gaps, and web findings checked
    against the Knowledge Base (app/stateless_answer.py)."""
    return await answer_without_memory(
        message, link_results, knowledge_base=get_knowledge_base(), settings=settings
    )


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
    """Health check for database connectivity and service status.

    Names the service: the website and this assistant both answer on /health on the same
    domain, so a reply has to say which one it came from.
    """
    try:
        # Execute a simple query to verify the MySQL connection
        db.execute(text("SELECT 1"))
        return {"status": "ok", "service": "iyobo", "database": "connected"}
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed"
        )


TELEGRAM_MAX_MESSAGE_CHARS = 4096


def split_telegram_message(text: str, limit: int = TELEGRAM_MAX_MESSAGE_CHARS) -> list[str]:
    """Split a reply into parts Telegram accepts, breaking at line breaks, then spaces."""
    parts: list[str] = []
    remaining = text
    while len(remaining) > limit:
        cut = remaining.rfind("\n", 0, limit)
        if cut <= 0:
            cut = remaining.rfind(" ", 0, limit)
        if cut <= 0:
            cut = limit
        parts.append(remaining[:cut].rstrip())
        remaining = remaining[cut:].lstrip()
    if remaining:
        parts.append(remaining)
    return parts


async def send_telegram_message(chat_id, text: str) -> bool:
    """Send a reply, split to fit Telegram's size limit. Returns False if Telegram refused any part."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        for part in split_telegram_message(text):
            try:
                response = await client.post(
                    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                    json={"chat_id": chat_id, "text": part},
                )
            except httpx.HTTPError as exc:
                # The exception text includes the request URL, which contains the bot token.
                logger.error("Telegram sendMessage failed: %s", exc.__class__.__name__)
                return False
            if response.status_code != 200:
                logger.error("Telegram sendMessage returned HTTP %s: %s", response.status_code, response.text[:200])
                return False
    return True


@app.post("/telegram/webhook", tags=["Telegram"])
async def telegram_webhook(request: Request):
    """
    Receive updates from Telegram and answer text messages with Iyobo.

    Telegram sends the secret registered with setWebhook (scripts/set_telegram_webhook.py) in the
    X-Telegram-Bot-Api-Secret-Token header. Requests without it are refused, so no one else can use
    the bot to spend AI credit or message arbitrary chats. Updates the bot doesn't answer still get
    a 200, because Telegram keeps retrying any other response.
    """
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not configured")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Telegram configuration missing")

    expected_secret = settings.TELEGRAM_WEBHOOK_SECRET
    if not expected_secret:
        logger.error("TELEGRAM_WEBHOOK_SECRET not configured; refusing Telegram updates")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Telegram webhook secret not configured")
    received_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not hmac.compare_digest(received_secret.encode("utf-8"), expected_secret.encode("utf-8")):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid Telegram secret")

    try:
        data = await request.json()
    except ValueError:
        return {"status": "ignored"}

    message = data.get("message") if isinstance(data, dict) else None
    chat = message.get("chat") if isinstance(message, dict) else None
    chat_id = chat.get("id") if isinstance(chat, dict) else None
    sender = message.get("from") if isinstance(message, dict) else None
    sender_id = sender.get("id") if isinstance(sender, dict) else None
    user_text = message.get("text") if isinstance(message, dict) else None
    if chat_id is None or not isinstance(user_text, str) or not user_text.strip():
        return {"status": "ignored"}  # stickers, photos, joins, edits, malformed updates

    logger.info(f"Telegram message from {chat_id}: {user_text}")
    try:
        # Telegram ids come only through the verified webhook, so they're safe to remember people by.
        reply, _ = await ask_iyobo(user_text, user_id=f"telegram:{sender_id if sender_id is not None else chat_id}")
        ai_reply = format_reply(reply)
    except GrokError as e:
        logger.error(f"AI Service Error: {e}")
        ai_reply = AI_UNAVAILABLE_REPLY

    await send_telegram_message(chat_id, ai_reply)
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(payload: ChatRequest):
    """Answer a chat message with Grok, using the Knowledge Base first and web search to fill gaps."""
    logger.info(f"Received message from user {payload.user_id}: {payload.message}")

    ctx = payload.context if isinstance(payload.context, dict) else {}
    # Summaries of pages the user linked, fetched by the frontend.
    link_results = ctx.get("search_results")
    if not isinstance(link_results, list):
        link_results = []

    try:
        reply, kb_sources = await ask_iyobo(payload.message, link_results, user_id=web_user_id(payload.user_id))
    except GrokNotConfigured:
        logger.error("XAI_API_KEY is not set; Iyobo cannot answer")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI assistant is not configured")
    except GrokError as e:
        logger.error(f"AI Service Error: {e}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="AI Service unreachable")

    return {
        "reply": format_reply(reply),
        "intent": "dynamic_ai",
        "sources": reply.citations,
        "knowledge_base_sources": kb_sources,
    }


# ── Knowledge review (project owner only) ───────────────────────────────────


class ReviewRequest(BaseModel):
    note: Optional[str] = Field(None, max_length=1000, description="Why it was approved or rejected")


def require_admin(request: Request) -> None:
    """Allow only `Authorization: Bearer <IYOBO_ADMIN_TOKEN>`. Closed to everyone while no token is set."""
    token = settings.IYOBO_ADMIN_TOKEN
    scheme, _, supplied = (request.headers.get("authorization") or "").partition(" ")
    if not token or scheme.lower() != "bearer" or not hmac.compare_digest(
        supplied.strip().encode("utf-8"), token.encode("utf-8")
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")


def _suggestion_json(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value.isoformat() if isinstance(value, datetime) else value for key, value in row.items()}


@app.get("/admin/knowledge-suggestions", tags=["Learning"])
async def list_knowledge_suggestions(
    request: Request,
    status_filter: str = Query("pending", alias="status"),
    limit: int = 50,
):
    """What users have taught Iyobo, by review status (pending, approved or rejected)."""
    require_admin(request)
    try:
        rows = await get_iyobo_agent().learning.list(status=status_filter, limit=limit)
    except ValueError as exc:
        # A literal: Starlette 1.x renamed the 422 constant, and both versions are in use.
        raise HTTPException(status_code=422, detail=str(exc))
    return {"suggestions": [_suggestion_json(row) for row in rows], "count": len(rows)}


async def _review_suggestion(request: Request, suggestion_id: int, approve: bool, body: Optional[ReviewRequest]):
    require_admin(request)
    agent = get_iyobo_agent()
    row = await agent.learning.review(suggestion_id, approve=approve, reviewer_note=body.note if body else None)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No pending suggestion with that id.")
    if approve:
        await agent.refresh_learned()  # searchable straight away
    return {"suggestion": _suggestion_json(row)}


@app.post("/admin/knowledge-suggestions/{suggestion_id}/approve", tags=["Learning"])
async def approve_knowledge_suggestion(suggestion_id: int, request: Request, body: Optional[ReviewRequest] = None):
    """Approve a suggestion: Iyobo can use it right away, and the export script adds it to the Knowledge Base."""
    return await _review_suggestion(request, suggestion_id, True, body)


@app.post("/admin/knowledge-suggestions/{suggestion_id}/reject", tags=["Learning"])
async def reject_knowledge_suggestion(suggestion_id: int, request: Request, body: Optional[ReviewRequest] = None):
    """Reject a suggestion. It stays on record but is never used."""
    return await _review_suggestion(request, suggestion_id, False, body)


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
        data = await create_response(
            api_key=settings.XAI_API_KEY,
            base_url=settings.XAI_BASE_URL,
            payload=build_payload(
                model=settings.XAI_MODEL,
                instructions="You are a UI/UX expert that generates clean, semantic HTML markup. Focus on accessibility, responsiveness, and modern design patterns.",
                message=prompt,
                web_search=False,
                temperature=0.7,
            ),
            timeout=settings.XAI_TIMEOUT_SECONDS,
        )
        return parse_response(data).text
    except GrokError as e:
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
