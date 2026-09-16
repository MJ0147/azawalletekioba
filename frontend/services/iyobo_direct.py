"""
Iyobo on the website when no assistant service is deployed.

With XAI_API_KEY set, the site chat asks Grok directly, using the same logic as the assistant's
answers without memory (services/stateless_answer.py, synced from ai_assistant/app): the Knowledge
Base copy is the main source, web search fills gaps, and web findings are checked against the
Knowledge Base before they're used. It doesn't remember visitors; for that, deploy the assistant
service and set AI_ASSISTANT_URL.
"""

from __future__ import annotations

import os
from types import SimpleNamespace
from typing import Any, Optional

from services import kb_fallback
from services.stateless_answer import answer_without_memory, format_reply


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name, "").strip().lower()
    return default if not value else value in {"1", "true", "yes", "on"}


def is_configured() -> bool:
    return bool(os.getenv("XAI_API_KEY", "").strip())


def settings() -> SimpleNamespace:
    """The settings answering without memory needs, read from the environment with the assistant's defaults."""
    return SimpleNamespace(
        XAI_API_KEY=os.getenv("XAI_API_KEY", "").strip(),
        XAI_BASE_URL=os.getenv("XAI_BASE_URL", "https://api.x.ai/v1"),
        XAI_MODEL=os.getenv("XAI_MODEL", "grok-4.6"),
        XAI_TIMEOUT_SECONDS=float(os.getenv("XAI_TIMEOUT_SECONDS", "60")),
        XAI_WEB_SEARCH=_env_bool("XAI_WEB_SEARCH", True),
        WEB_REQUIRE_KB_CONFIRMATION=_env_bool("WEB_REQUIRE_KB_CONFIRMATION", False),
        KNOWLEDGE_BASE_TOP_K=int(os.getenv("KNOWLEDGE_BASE_TOP_K", "6")),
        KNOWLEDGE_BASE_MAX_CHARS=int(os.getenv("KNOWLEDGE_BASE_MAX_CHARS", "12000")),
    )


async def answer(message: str, link_results: Optional[list[dict[str, Any]]] = None) -> str:
    """Grok's reply to a chat message, with its web sources listed. Raises GrokError if xAI fails."""
    reply, _ = await answer_without_memory(
        message, link_results, knowledge_base=kb_fallback.get_knowledge_base(), settings=settings()
    )
    return format_reply(reply)
