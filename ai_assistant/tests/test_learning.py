import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from pydantic import Field

from app import main
from app.grok_client import GrokReply
from app.iyobo_agent import AGENT_NAME, APP_NAME, LEARNED_SOURCE, MEMORY_STATE_KEY, MAX_MEMORY_NOTES, IyoboAgent
from app.learning_store import async_database_url
from config import settings

ADMIN_TOKEN = "test-admin-token"
VISITOR = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"


@pytest.fixture(scope="module")
def client():
    return TestClient(main.app)


@pytest.fixture
def agent(tmp_path, monkeypatch):
    """A real learning agent on a throwaway SQLite database; no AI calls are made."""
    monkeypatch.setattr(settings, "IYOBO_MEMORY_DB_URL", f"sqlite:///{tmp_path / 'memory.db'}")
    monkeypatch.setattr(settings, "IYOBO_MAX_SUGGESTIONS_PER_DAY", 2)
    instance = IyoboAgent(settings=settings, instruction="You are Iyobo.", knowledge_base=main.get_knowledge_base)
    monkeypatch.setattr(main, "get_iyobo_agent", lambda: instance)
    return instance


def _admin(token=ADMIN_TOKEN):
    return {"Authorization": f"Bearer {token}"}


# ── Database URLs ─────────────────────────────────────────────────────────────

def test_postgres_urls_use_asyncpg_and_the_private_schema():
    url, args = async_database_url("postgresql://u:p@aws-0-eu.pooler.supabase.com:5432/postgres?sslmode=require")
    assert url == "postgresql+asyncpg://u:p@aws-0-eu.pooler.supabase.com:5432/postgres"
    assert args["server_settings"] == {"search_path": "iyobo"}
    assert args["ssl"] == "require"


def test_sqlite_urls_use_aiosqlite_and_other_databases_are_refused():
    assert async_database_url("sqlite:///./memory.db")[0] == "sqlite+aiosqlite:///./memory.db"
    with pytest.raises(ValueError):
        async_database_url("mysql://u:p@host/db")


# ── Memory ──────────────────────────────────────────────────────────────────

def test_memory_is_kept_per_person_across_conversations(agent):
    async def scenario():
        await agent.session_service.create_session(
            app_name=APP_NAME, user_id="web:osaro", session_id="2000-01-01",
            state={MEMORY_STATE_KEY: ["Name is Osaro"]},
        )
        return await agent._session_for("web:osaro"), await agent._session_for("web:someone-else")

    today, stranger = asyncio.run(scenario())
    assert today.id != "2000-01-01"
    assert today.state.get(MEMORY_STATE_KEY) == ["Name is Osaro"]
    assert not stranger.state.get(MEMORY_STATE_KEY)


def test_remember_and_forget_tools(agent):
    context = SimpleNamespace(state={}, user_id="web:osaro")

    async def scenario():
        await agent.remember_about_user("Name is Osaro", context)
        await agent.remember_about_user("  Name   is Osaro ", context)  # same note, different spacing
        for number in range(MAX_MEMORY_NOTES + 5):
            await agent.remember_about_user(f"note {number}", context)
        kept = list(context.state[MEMORY_STATE_KEY])
        await agent.forget_about_user(context)
        return kept

    kept = asyncio.run(scenario())
    assert len(kept) == MAX_MEMORY_NOTES
    assert kept[-1] == f"note {MAX_MEMORY_NOTES + 4}"
    assert context.state[MEMORY_STATE_KEY] == []


# ── Agent graph ─────────────────────────────────────────────────────────────

class ScriptedModel(BaseLlm):
    """Stands in for Grok: returns scripted replies and records what each request contained."""

    model: str = "scripted"
    replies: list = Field(default_factory=list)
    requests: list = Field(default_factory=list)

    async def generate_content_async(self, llm_request, stream=False):
        self.requests.append([content.model_copy(deep=True) for content in llm_request.contents])
        yield self.replies.pop(0)


def _says(text):
    return LlmResponse(content=types.Content(role="model", parts=[types.Part(text=text)]))


def _calls(name, **args):
    call = types.FunctionCall(name=name, args=args)
    return LlmResponse(content=types.Content(role="model", parts=[types.Part(function_call=call)]))


def _brief(request):
    """The JSON brief the JoinNode handed to the strategy agent (the last user text in the request)."""
    texts = [part.text for content in request if content.role == "user" for part in content.parts if part.text]
    return json.loads(texts[-1])


@pytest.fixture
def graph_agent(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "IYOBO_MEMORY_DB_URL", f"sqlite:///{tmp_path / 'memory.db'}")
    monkeypatch.setattr(settings, "XAI_API_KEY", "test-key")
    model = ScriptedModel()
    instance = IyoboAgent(settings=settings, instruction="You are Iyobo.", knowledge_base=main.get_knowledge_base, model=model)
    return instance, model


def _chat(agent, *args):
    return asyncio.run(asyncio.wait_for(agent.chat(*args), timeout=60))  # a stalled join fails instead of hanging


def test_each_turn_fetches_in_parallel_then_joins_before_the_strategy_agent(graph_agent):
    agent, model = graph_agent
    edges = {(edge.from_node.name, edge.to_node.name) for edge in agent.workflow.graph.edges}
    fetches = {"message", "memory", "knowledge_base", "linked_pages"}
    assert edges == {("__START__", f) for f in fetches} | {(f, "brief") for f in fetches} | {("brief", AGENT_NAME)}

    model.replies = [_says("Dog is ekita.")]
    links = [{"name": "Dog page", "url": "https://example.com/dog", "snippet": "About dogs"}]
    reply, kb_sources = _chat(agent, "web:osaro", "Edo word for dog?", links)

    assert reply.text == "Dog is ekita."
    assert any(source.startswith("Language Academy/") for source in kb_sources)
    brief = _brief(model.requests[0])
    assert brief["message"] == "Edo word for dog?"
    assert brief["memory"] == []
    assert "[KB1]" in brief["knowledge_base"]["excerpts"]
    assert brief["linked_pages"] == [{"name": "Dog page", "url": "https://example.com/dog", "snippet": "About dogs"}]


def test_the_strategy_agent_remembers_people_and_follows_the_conversation(graph_agent):
    agent, model = graph_agent
    model.replies = [_calls("remember_about_user", note="Name is Osaro"), _says("Koyo Osaro! Dog is ekita."), _says("Seven is ihinrọn.")]

    _chat(agent, "web:osaro", "I'm Osaro. Edo word for dog?")
    reply, _ = _chat(agent, "web:osaro", "and seven?")

    assert reply.text == "Seven is ihinrọn."
    second_turn = model.requests[2]
    assert _brief(second_turn)["memory"] == ["Name is Osaro"]
    earlier = [part.text for content in second_turn if content.role == "model" for part in content.parts if part.text]
    assert "Koyo Osaro! Dog is ekita." in earlier
    assert asyncio.run(agent._session_for("web:osaro")).state.get(MEMORY_STATE_KEY) == ["Name is Osaro"]


# ── Review queue ────────────────────────────────────────────────────────────

def test_taught_knowledge_waits_for_approval_and_is_rate_limited(agent):
    context = SimpleNamespace(state={}, user_id="telegram:777")

    async def scenario():
        first = await agent.suggest_knowledge("Says koyo means hello", context, edo="koyo", english="hello")
        second = await agent.suggest_knowledge("second", context)
        third = await agent.suggest_knowledge("third", context)
        pending = await agent.learning.list("pending")
        await agent.refresh_learned()
        before = [chunk.source for chunk, _ in agent.knowledge_base().search("koyo hello", limit=5)]
        return first, second, third, pending, before

    first, second, third, pending, before = asyncio.run(scenario())
    assert first["queued"] and second["queued"]
    assert third["queued"] is False  # daily limit of 2 in this test
    row = next(r for r in pending if r["id"] == first["suggestion_id"])
    assert row["source_channel"] == "telegram"
    assert row["user_ref"] and "777" not in row["user_ref"]
    assert LEARNED_SOURCE not in before


def test_admin_endpoints_are_closed_without_the_token(client, agent, monkeypatch):
    monkeypatch.setattr(settings, "IYOBO_ADMIN_TOKEN", "")
    assert client.get("/admin/knowledge-suggestions", headers=_admin()).status_code == 401
    monkeypatch.setattr(settings, "IYOBO_ADMIN_TOKEN", ADMIN_TOKEN)
    assert client.get("/admin/knowledge-suggestions").status_code == 401
    assert client.get("/admin/knowledge-suggestions", headers=_admin("wrong")).status_code == 401
    assert client.get("/admin/knowledge-suggestions", headers=_admin()).status_code == 200


def test_owner_approval_makes_knowledge_searchable(client, agent, monkeypatch):
    monkeypatch.setattr(settings, "IYOBO_ADMIN_TOKEN", ADMIN_TOKEN)
    good = asyncio.run(agent.learning.suggest(note="koyo means hello", edo="koyo", english="hello", user_id="web:a"))
    bad = asyncio.run(agent.learning.suggest(note="wrong claim", user_id="web:b"))

    listed = client.get("/admin/knowledge-suggestions", params={"status": "pending"}, headers=_admin()).json()
    assert {s["id"] for s in listed["suggestions"]} == {good, bad}

    approved = client.post(f"/admin/knowledge-suggestions/{good}/approve", json={"note": "Correct"}, headers=_admin())
    assert approved.status_code == 200 and approved.json()["suggestion"]["status"] == "approved"
    assert client.post(f"/admin/knowledge-suggestions/{good}/approve", headers=_admin()).status_code == 404
    rejected = client.post(f"/admin/knowledge-suggestions/{bad}/reject", headers=_admin())
    assert rejected.json()["suggestion"]["status"] == "rejected"

    top = agent.knowledge_base().search("koyo hello", limit=1)
    assert top and top[0][0].source == LEARNED_SOURCE


def test_unknown_status_filter_is_rejected(client, agent, monkeypatch):
    monkeypatch.setattr(settings, "IYOBO_ADMIN_TOKEN", ADMIN_TOKEN)
    assert client.get("/admin/knowledge-suggestions", params={"status": "everything"}, headers=_admin()).status_code == 422


# ── Routing ─────────────────────────────────────────────────────────────────

@pytest.fixture
def routes(monkeypatch):
    """Record which path answered: the learning agent (with its user id) or the stateless fallback."""
    calls = {"agent": [], "stateless": 0}

    async def agent_chat(user_id, message, link_results=None):
        calls["agent"].append(user_id)
        return GrokReply(text="from the agent"), []

    async def stateless(message, link_results=None):
        calls["stateless"] += 1
        return GrokReply(text="without memory"), []

    monkeypatch.setattr(main, "get_iyobo_agent", lambda: SimpleNamespace(chat=agent_chat))
    monkeypatch.setattr(main, "ask_iyobo_stateless", stateless)
    return calls


def test_website_visitors_with_an_id_get_the_learning_agent(client, routes):
    response = client.post("/chat", json={"message": "hello", "user_id": VISITOR})
    assert response.json()["reply"] == "from the agent"
    assert routes["agent"] == [f"web:{VISITOR}"]


def test_visitors_without_a_valid_id_are_answered_without_memory(client, routes):
    for user_id in (None, "short", "telegram:777"):  # a web request can't pose as a Telegram user
        payload = {"message": "hello"} if user_id is None else {"message": "hello", "user_id": user_id}
        assert client.post("/chat", json=payload).json()["reply"] == "without memory"
    assert routes["agent"] == [] and routes["stateless"] == 3


def test_memory_outage_falls_back_to_answering_without_memory(client, monkeypatch):
    async def broken(user_id, message, link_results=None):
        raise ConnectionError("database unreachable")

    async def stateless(message, link_results=None):
        return GrokReply(text="without memory"), []

    monkeypatch.setattr(main, "get_iyobo_agent", lambda: SimpleNamespace(chat=broken))
    monkeypatch.setattr(main, "ask_iyobo_stateless", stateless)
    response = client.post("/chat", json={"message": "hello", "user_id": VISITOR})
    assert response.status_code == 200 and response.json()["reply"] == "without memory"
