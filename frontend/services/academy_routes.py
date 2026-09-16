"""HTTP routes for the Edo Language Academy institute: wallet sign-in, grade exams, points and IDIA conversions."""

from __future__ import annotations

import logging
import os
from typing import Any, Awaitable, Callable, Optional

import sqlalchemy as sa
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse

from services import academy_auth, academy_institute, telegram_login, ton_proof
from services.academy_institute import AcademyError
from services.academy_store import AcademyStore

logger = logging.getLogger("ekioba.academy")
router = APIRouter()

_store: Optional[AcademyStore] = None
_store_url = ""


def get_store() -> AcademyStore:
    """The Academy database (ACADEMY_DATABASE_URL, else DATABASE_URL), opened once per URL."""
    global _store, _store_url
    url = (os.getenv("ACADEMY_DATABASE_URL") or os.getenv("DATABASE_URL") or "").strip()
    if not url:
        raise AcademyError(503, "Grades and points aren't set up on this site yet.")
    if _store is None or _store_url != url:
        try:
            _store = AcademyStore(url)
        except ValueError as exc:
            logger.error("Academy database URL is unusable: %s", exc)
            raise AcademyError(503, "Grades and points aren't set up on this site yet.") from exc
        _store_url = url
    return _store


async def _respond(action: Callable[[], Awaitable[Any]], status_code: int = 200) -> JSONResponse:
    try:
        return JSONResponse(await action(), status_code=status_code)
    except AcademyError as exc:
        return JSONResponse({"error": exc.message}, status_code=exc.status_code)
    except (sa.exc.SQLAlchemyError, OSError) as exc:
        logger.error("Academy database unavailable: %s: %s", exc.__class__.__name__, exc)
        return JSONResponse({"error": "Academy records are unavailable right now. Please try again shortly."}, status_code=503)


async def _json_body(request: Request) -> dict[str, Any]:
    try:
        body = await request.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


def _secret() -> str:
    secret = academy_auth.session_secret()
    if not secret:
        raise AcademyError(503, "Wallet sign-in isn't set up on this site yet.")
    return secret


def _wallet(request: Request) -> str:
    wallet = academy_auth.read_session(request.cookies.get(academy_auth.SESSION_COOKIE), academy_auth.session_secret())
    if not wallet:
        raise AcademyError(401, "Sign in with your TON wallet to take graded exams.")
    return wallet


def _require_admin(request: Request) -> None:
    """EKIOBA admins logged in with Telegram, or a `Bearer <ACADEMY_ADMIN_TOKEN>` header."""
    if not (academy_auth.is_admin(request.headers.get("authorization")) or telegram_login.request_is_admin(request)):
        raise AcademyError(401, "Unauthorized")


def _host(request: Request) -> str:
    return request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc


def _is_https(request: Request) -> bool:
    proto = request.headers.get("x-forwarded-proto", "").split(",")[0].strip() or request.url.scheme
    return proto == "https" or os.getenv("PUBLIC_BASE_URL", "").startswith("https://")


# ── Sign-in ──────────────────────────────────────────────────────────────────


@router.get("/api/academy/auth/challenge")
async def academy_sign_in_challenge() -> JSONResponse:
    """A one-time payload for the wallet to sign (TON Connect ton_proof)."""

    async def action() -> dict[str, str]:
        return {"payload": ton_proof.new_payload(_secret())}

    return await _respond(action)


@router.post("/api/academy/auth/verify")
async def academy_sign_in(request: Request) -> JSONResponse:
    """Check the wallet's signed proof and start a session for that wallet."""
    body = await _json_body(request)
    proof = body.get("proof")
    try:
        secret = _secret()
        wallet = ton_proof.verify_proof(
            address=str(body.get("address") or ""),
            proof=proof if isinstance(proof, dict) else {},
            state_init=str(body.get("state_init") or ""),
            allowed_domains=academy_auth.proof_domains(_host(request)),
            secret=secret,
        )
    except AcademyError as exc:
        return JSONResponse({"error": exc.message}, status_code=exc.status_code)
    except ton_proof.TonProofError as exc:
        return JSONResponse({"error": f"Wallet sign-in failed: {exc}."}, status_code=401)

    response = JSONResponse({"wallet": wallet, "wallet_display": academy_institute.display_address(wallet)})
    response.set_cookie(
        academy_auth.SESSION_COOKIE,
        academy_auth.make_session(wallet, secret),
        max_age=academy_auth.SESSION_SECONDS,
        httponly=True,
        samesite="lax",
        secure=_is_https(request),
    )
    return response


@router.post("/api/academy/auth/logout")
async def academy_sign_out() -> JSONResponse:
    response = JSONResponse({"signed_out": True})
    response.delete_cookie(academy_auth.SESSION_COOKIE)
    return response


# ── Learner ──────────────────────────────────────────────────────────────────


@router.get("/api/academy/me")
async def academy_me(request: Request) -> JSONResponse:
    return await _respond(lambda: academy_institute.profile(get_store(), _wallet(request)))


@router.post("/api/academy/exams")
async def academy_start_exam(request: Request) -> JSONResponse:
    body = await _json_body(request)
    return await _respond(lambda: academy_institute.start_exam(get_store(), _wallet(request), body.get("grade")))


@router.post("/api/academy/exams/{attempt_id}/answer")
async def academy_answer(attempt_id: str, request: Request) -> JSONResponse:
    body = await _json_body(request)
    return await _respond(
        lambda: academy_institute.answer_question(get_store(), _wallet(request), attempt_id, body.get("index"), body.get("choice"))
    )


@router.post("/api/academy/conversions")
async def academy_request_conversion(request: Request) -> JSONResponse:
    return await _respond(lambda: academy_institute.request_conversion(get_store(), _wallet(request)), status_code=201)


# ── Review (EKIOBA team) ─────────────────────────────────────────────────────


@router.get("/api/academy/admin/conversions")
async def academy_admin_conversions(request: Request, status: str = "pending", limit: int = 100) -> JSONResponse:
    async def action() -> dict[str, Any]:
        _require_admin(request)
        return {"conversions": await academy_institute.list_conversions(get_store(), status, limit)}

    return await _respond(action)


@router.post("/api/academy/admin/conversions/{conversion_id}/paid")
async def academy_admin_mark_paid(conversion_id: int, request: Request) -> JSONResponse:
    body = await _json_body(request)

    async def action() -> dict[str, Any]:
        _require_admin(request)
        return await academy_institute.review_conversion(
            get_store(), conversion_id, paid=True, tx_hash=body.get("tx_hash"), note=body.get("note")
        )

    return await _respond(action)


@router.post("/api/academy/admin/conversions/{conversion_id}/reject")
async def academy_admin_reject(conversion_id: int, request: Request) -> JSONResponse:
    body = await _json_body(request)

    async def action() -> dict[str, Any]:
        _require_admin(request)
        return await academy_institute.review_conversion(get_store(), conversion_id, paid=False, tx_hash=None, note=body.get("note"))

    return await _respond(action)


@router.get("/academy/admin")
async def academy_admin_page() -> RedirectResponse:
    """Conversions are reviewed in the site admin area, alongside orders and Iyobo's knowledge queue."""
    return RedirectResponse("/admin#conversions", status_code=307)
