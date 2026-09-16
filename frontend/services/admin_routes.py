"""Telegram login pages and the site admin area (/admin), open to the Telegram accounts listed as admins."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from services import telegram_login
from services.academy_auth import SESSION_SECONDS, session_secret

logger = logging.getLogger("ekioba.admin")
router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


def _origin(request: Request) -> str:
    base = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
    if base:
        return base
    proto = request.headers.get("x-forwarded-proto", "").split(",")[0].strip() or request.url.scheme or "https"
    host = (request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc).split(",")[0].strip()
    return f"{proto}://{host}"


def safe_next(value: Any) -> str:
    """Only paths on this site, so a login link can't send people to another website."""
    path = str(value or "")
    if not path.startswith("/") or path.startswith("//") or "\\" in path:
        return "/"
    return path


def _account(user: Optional[telegram_login.TelegramUser]) -> dict[str, Any]:
    if user is None:
        return {"signed_in": False, "is_admin": False}
    return {"signed_in": True, "id": user.id, "username": user.username, "is_admin": telegram_login.is_admin(user)}


# ── Telegram login ───────────────────────────────────────────────────────────


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, next: str = "/", error: str = "") -> HTMLResponse:
    destination = safe_next(next)
    return templates.TemplateResponse(request, "login.html", {
        "bot_username": telegram_login.bot_username(),
        "auth_url": f"{_origin(request)}/auth/telegram/callback?next={quote(destination, safe='/')}",
        "configured": telegram_login.is_configured(),
        "account": _account(telegram_login.current_user(request)),
        "error": error[:200],
    })


@router.get("/auth/telegram/callback")
async def telegram_callback(request: Request) -> RedirectResponse:
    """Where Telegram sends people after they log in with the widget."""
    params = dict(request.query_params)
    destination = safe_next(params.get("next", "/"))
    secret = session_secret()
    try:
        if not secret:
            raise telegram_login.TelegramLoginError("Telegram login isn't set up on this site yet")
        user = telegram_login.verify_login(params, telegram_login.bot_token())
    except telegram_login.TelegramLoginError as exc:
        return RedirectResponse(f"/login?next={quote(destination, safe='/')}&error={quote(str(exc))}", status_code=303)
    response = RedirectResponse(destination, status_code=303)
    response.set_cookie(
        telegram_login.SESSION_COOKIE,
        telegram_login.session_for(user, secret),
        max_age=SESSION_SECONDS,
        httponly=True,
        samesite="lax",
        secure=_origin(request).startswith("https://"),
    )
    return response


@router.get("/api/telegram/me")
async def telegram_me(request: Request) -> JSONResponse:
    return JSONResponse(_account(telegram_login.current_user(request)))


@router.post("/api/telegram/logout")
async def telegram_logout() -> JSONResponse:
    response = JSONResponse({"signed_out": True})
    response.delete_cookie(telegram_login.SESSION_COOKIE)
    return response


# ── Admin area ───────────────────────────────────────────────────────────────


@router.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "admin.html", {"account": _account(telegram_login.current_user(request))})


def assistant_base_url(origin: str) -> str:
    """Iyobo's assistant service: an explicit URL, else the "iyobo" service on this domain on Vercel."""
    base = (os.getenv("NEXT_PUBLIC_IYOBO_API_URL") or os.getenv("AI_ASSISTANT_URL") or "").strip()
    if not base and os.getenv("VERCEL"):
        base = f"{origin}/iyobo"
    return (base or "http://localhost:8005").rstrip("/")


async def send_to_assistant(method: str, url: str, token: str, *, params: Optional[dict[str, Any]] = None, body: Optional[dict[str, Any]] = None) -> tuple[int, Any]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.request(method, url, params=params, json=body, headers={"Authorization": f"Bearer {token}"})
    try:
        return response.status_code, response.json()
    except ValueError:
        return response.status_code, {"error": "Iyobo's assistant returned an unreadable response."}


async def _knowledge_request(request: Request, method: str, path: str, *, params: Optional[dict[str, Any]] = None, body: Optional[dict[str, Any]] = None) -> JSONResponse:
    """Pass an admin's knowledge-review request to Iyobo's assistant, which keeps the review queue."""
    if not telegram_login.request_is_admin(request):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    token = os.getenv("IYOBO_ADMIN_TOKEN", "").strip()
    if not token:
        return JSONResponse({"error": "Set IYOBO_ADMIN_TOKEN on this site to review Iyobo's knowledge queue."}, status_code=503)
    try:
        status, data = await send_to_assistant(method, f"{assistant_base_url(_origin(request))}{path}", token, params=params, body=body)
    except httpx.HTTPError as exc:
        logger.warning("Iyobo's assistant couldn't be reached for knowledge review: %s", exc.__class__.__name__)
        return JSONResponse({"error": "Iyobo's assistant service couldn't be reached."}, status_code=502)
    if isinstance(data, dict) and "detail" in data and "error" not in data:
        data = {**data, "error": str(data["detail"])}
    return JSONResponse(data, status_code=status if status < 500 else 502)


@router.get("/api/admin/knowledge-suggestions")
async def admin_knowledge_suggestions(request: Request, status: str = "pending") -> JSONResponse:
    return await _knowledge_request(request, "GET", "/admin/knowledge-suggestions", params={"status": status})


@router.post("/api/admin/knowledge-suggestions/{suggestion_id}/{action}")
async def admin_review_knowledge(suggestion_id: int, action: str, request: Request) -> JSONResponse:
    if action not in {"approve", "reject"}:
        return JSONResponse({"error": "Unknown action."}, status_code=404)
    try:
        body = await request.json()
    except ValueError:
        body = {}
    note = body.get("note") if isinstance(body, dict) else None
    return await _knowledge_request(request, "POST", f"/admin/knowledge-suggestions/{suggestion_id}/{action}", body={"note": note or None})
