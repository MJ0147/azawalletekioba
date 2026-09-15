"""
xAI Grok client — the only AI provider behind Iyobo.

Calls the xAI Responses API (POST /v1/responses) over plain HTTP. With web search enabled,
Grok decides for itself when to search; the pages it used come back as url_citation
annotations, which parse_response collects so callers can list them after the answer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import httpx


class GrokError(RuntimeError):
    """The xAI request failed or returned something unusable."""


class GrokNotConfigured(GrokError):
    """XAI_API_KEY is not set."""


@dataclass
class GrokReply:
    text: str
    citations: list[str] = field(default_factory=list)  # web page URLs, in first-cited order


def build_payload(
    *,
    model: str,
    instructions: str,
    message: str,
    web_search: bool,
    temperature: Optional[float] = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "instructions": instructions,
        "input": [{"role": "user", "content": message}],
        # Chats contain users' messages; don't keep them on xAI's side (the default is 30 days).
        "store": False,
    }
    if web_search:
        payload["tools"] = [{"type": "web_search"}]
        # List sources after the answer instead of inline [[n]](url) markdown, which the
        # site's chat bubble and Telegram would show as raw text.
        payload["include"] = ["no_inline_citations"]
    if temperature is not None:
        payload["temperature"] = temperature
    return payload


def parse_response(data: dict[str, Any]) -> GrokReply:
    texts: list[str] = []
    citations: list[str] = []

    def add_citation(url: Any) -> None:
        url = str(url or "").strip()
        if url and url not in citations:
            citations.append(url)

    for item in data.get("output") or []:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for part in item.get("content") or []:
            if not isinstance(part, dict) or part.get("type") != "output_text":
                continue
            if part.get("text"):
                texts.append(str(part["text"]))
            for annotation in part.get("annotations") or []:
                if isinstance(annotation, dict) and annotation.get("type") == "url_citation":
                    add_citation(annotation.get("url"))

    # The xAI SDK exposes a flat citations list; accept it too if the raw response carries one.
    for url in data.get("citations") or []:
        add_citation(url)

    text = "\n\n".join(texts).strip()
    if not text:
        raise GrokError(f"xAI response contained no text (status={data.get('status')!r})")
    return GrokReply(text=text, citations=citations)


async def create_response(
    *, api_key: str, base_url: str, payload: dict[str, Any], timeout: float
) -> dict[str, Any]:
    if not api_key:
        raise GrokNotConfigured("XAI_API_KEY is not set")
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                f"{base_url.rstrip('/')}/responses",
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
            )
    except httpx.HTTPError as exc:
        raise GrokError(f"xAI request failed: {exc.__class__.__name__}: {exc}") from exc
    if response.status_code >= 400:
        raise GrokError(f"xAI returned HTTP {response.status_code}: {response.text[:300]}")
    try:
        return response.json()
    except ValueError as exc:
        raise GrokError("xAI returned a non-JSON response") from exc
