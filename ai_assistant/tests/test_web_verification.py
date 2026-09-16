import asyncio
import json

import pytest

from app import iyobo_agent, main, web_verification
from app.iyobo_agent import IyoboAgent
from app.knowledge_base import Chunk, KnowledgeBase
from app.web_verification import (
    CONFIRMED,
    CONTRADICTED,
    NOT_COVERED,
    WebVerificationError,
    parse_claims,
    verify_web_findings,
)
from config import settings

DOG = Chunk("Language Academy/edo-animals-dataset.json", "dog", "edo: ekita; english: dog")
OBA = Chunk("Benin History/benin-obas-museum-catalogue.md", "Ewuare II", "Oba Ewuare II was crowned in 2016.")
KB = KnowledgeBase(None, [DOG, OBA])
WEB_PAGE = "https://example.com/edo"


def grok_says(text, *, searched=False, citations=()):
    """A Responses API reply, optionally showing that Grok searched the web."""
    output = [{"type": "web_search_call", "status": "completed"}] if searched else []
    annotations = [{"type": "url_citation", "url": url} for url in citations]
    output.append({"type": "message", "content": [{"type": "output_text", "text": text, "annotations": annotations}]})
    return {"status": "completed", "output": output}


def verdicts(*claims):
    """The checker's JSON reply: (claim, status, kb_ref, knowledge_base_says) tuples."""
    items = [{"claim": c, "status": s, "kb_ref": r, "knowledge_base_says": k} for c, s, r, k in claims]
    return grok_says(json.dumps({"claims": items}))


MIXED_VERDICTS = verdicts(
    ("Dog in Edo is ekue", CONTRADICTED, "KB1", "edo: ekita; english: dog"),
    ("Oba Ewuare II was crowned in 2016", CONFIRMED, "KB2", ""),
    ("EKIOBA ships to Ghana", NOT_COVERED, "", ""),
)


@pytest.fixture
def grok(monkeypatch):
    """A fake xAI API: answers with queued replies in order and records every request."""
    state = {"replies": [], "payloads": []}

    async def fake_create_response(*, api_key, base_url, payload, timeout):
        state["payloads"].append(payload)
        return state["replies"].pop(0)

    for module in (main, iyobo_agent, web_verification):
        monkeypatch.setattr(module, "create_response", fake_create_response)
    monkeypatch.setattr(main, "get_knowledge_base", lambda: KB)
    monkeypatch.setattr(settings, "XAI_API_KEY", "test-key")
    monkeypatch.setattr(settings, "XAI_WEB_SEARCH", True)
    monkeypatch.setattr(settings, "WEB_REQUIRE_KB_CONFIRMATION", False)
    return state


@pytest.fixture
def agent(grok, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "IYOBO_MEMORY_DB_URL", f"sqlite:///{tmp_path / 'memory.db'}")
    return IyoboAgent(settings=settings, instruction="You are Iyobo.", knowledge_base=lambda: KB)


# ── The check ───────────────────────────────────────────────────────────────

def test_verdicts_are_read_from_json_and_unclear_ones_are_never_confirmed():
    text = "```json\n" + json.dumps({"claims": [
        {"claim": "Dog is ekita", "status": "CONFIRMED", "kb_ref": "KB1"},
        {"claim": "Igue is in December", "status": "probably"},
    ]}) + "\n```"
    assert [claim.status for claim in parse_claims(text)] == [CONFIRMED, NOT_COVERED]
    for unreadable in ("Looks right to me!", '{"claims": []}', '{"claims": "all fine"}'):
        with pytest.raises(WebVerificationError):
            parse_claims(unreadable)


def test_findings_are_compared_with_matching_knowledge_base_excerpts(grok):
    grok["replies"] = [MIXED_VERDICTS]
    check = asyncio.run(verify_web_findings("Dog in Edo is ekue.", question="Edo word for dog", knowledge_base=KB, settings=settings))

    request = grok["payloads"][0]
    assert "tools" not in request  # the check itself never searches the web
    assert "edo: ekita; english: dog" in request["input"][0]["content"]
    assert check.kb_sources[0] == DOG.source
    assert [claim.status for claim in check.claims] == [CONTRADICTED, CONFIRMED, NOT_COVERED]


def test_findings_the_knowledge_base_says_nothing_about_are_unverified(grok):
    check = asyncio.run(verify_web_findings(
        "The 2027 festival starts on 20 December.", question="When is the festival?",
        knowledge_base=KnowledgeBase(None, []), settings=settings,
    ))
    assert [claim.status for claim in check.claims] == [NOT_COVERED]
    assert grok["payloads"] == []  # nothing to compare against, so no AI call


# ── The learning agent's web search ─────────────────────────────────────────

def test_agent_web_search_only_passes_on_what_the_knowledge_base_allows(agent, grok):
    grok["replies"] = [grok_says("Dog in Edo is ekue. ...", searched=True, citations=[WEB_PAGE]), MIXED_VERDICTS]
    result = asyncio.run(agent.search_web("Edo word for dog"))

    assert result["found"] is True
    assert result["verified_by_knowledge_base"] == ["Oba Ewuare II was crowned in 2016"]
    assert result["unverified_not_in_knowledge_base"] == ["EKIOBA ships to Ghana"]
    assert result["rejected_knowledge_base_disagrees"] == [
        {"web_said": "Dog in Edo is ekue", "knowledge_base_says": "edo: ekita; english: dog", "kb_ref": "KB1"}
    ]
    assert "answer" not in result  # the raw web answer never reaches the agent
    assert result["sources"] == [WEB_PAGE]


def test_agent_web_search_can_require_knowledge_base_confirmation(agent, grok, monkeypatch):
    monkeypatch.setattr(settings, "WEB_REQUIRE_KB_CONFIRMATION", True)
    grok["replies"] = [grok_says("...", searched=True, citations=[WEB_PAGE]), MIXED_VERDICTS]
    result = asyncio.run(agent.search_web("Edo word for dog"))

    assert "unverified_not_in_knowledge_base" not in result
    assert result["dropped_not_in_knowledge_base"] == 1
    assert result["verified_by_knowledge_base"] == ["Oba Ewuare II was crowned in 2016"]


def test_agent_web_search_uses_nothing_when_the_check_fails(agent, grok):
    grok["replies"] = [grok_says("Dog in Edo is ekue.", searched=True, citations=[WEB_PAGE]), grok_says("Looks right to me!")]
    result = asyncio.run(agent.search_web("Edo word for dog"))
    assert result == {"found": False, "error": "Web results couldn't be checked against the Knowledge Base, so they weren't used."}


# ── Answers without memory ──────────────────────────────────────────────────

def test_answers_that_used_the_web_are_rewritten_with_only_checked_findings(grok):
    grok["replies"] = [
        grok_says("Dog is ekue, and EKIOBA ships to Ghana.", searched=True, citations=[WEB_PAGE]),
        MIXED_VERDICTS,
        grok_says("Dog is ekita. The web says EKIOBA ships to Ghana, but that isn't verified."),
    ]
    reply, kb_sources = asyncio.run(main.ask_iyobo_stateless("Edo word for dog?"))

    first, check, final = grok["payloads"]
    assert first["tools"] == [{"type": "web_search"}]
    assert "tools" not in check and "tools" not in final
    instructions = final["instructions"]
    assert "Verified by the Knowledge Base (state as fact):\n- Oba Ewuare II was crowned in 2016" in instructions
    assert "Not in the Knowledge Base" in instructions and "- EKIOBA ships to Ghana" in instructions
    assert "Web said: Dog in Edo is ekue. Knowledge Base [KB1] says: edo: ekita; english: dog" in instructions
    assert instructions.count("ekue") == 1  # only as a rejected claim
    assert reply.text.startswith("Dog is ekita.")
    assert reply.citations == [WEB_PAGE]
    assert DOG.source in kb_sources


def test_answers_from_the_knowledge_base_alone_need_no_check(grok):
    grok["replies"] = [grok_says("Dog is ekita.")]
    reply, _ = asyncio.run(main.ask_iyobo_stateless("Edo word for dog?"))
    assert reply.text == "Dog is ekita." and len(grok["payloads"]) == 1


def test_answers_drop_all_web_findings_when_the_check_fails(grok):
    grok["replies"] = [
        grok_says("Dog is ekue.", searched=True, citations=[WEB_PAGE]),
        grok_says("not json"),
        grok_says("Dog is ekita."),
    ]
    reply, _ = asyncio.run(main.ask_iyobo_stateless("Edo word for dog?"))
    assert "couldn't be checked against the Knowledge Base" in grok["payloads"][2]["instructions"]
    assert reply.text == "Dog is ekita." and reply.citations == []
