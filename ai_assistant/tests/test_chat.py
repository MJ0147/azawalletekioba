import pytest
from fastapi.testclient import TestClient

from app import main
from app.grok_client import GrokError, GrokReply, build_payload, parse_response
from config import settings


@pytest.fixture(scope="module")
def client():
    return TestClient(main.app)


def test_chat_validation_empty_message(client):
    """An empty message results in a 422 Validation Error."""
    response = client.post("/chat", json={"message": ""})
    assert response.status_code == 422


def test_chat_missing_required_field(client):
    """Missing the message field results in a 422 error."""
    response = client.post("/chat", json={"user_id": "user_123"})
    assert response.status_code == 422


def test_chat_without_xai_key_returns_503(client, monkeypatch):
    monkeypatch.setattr(settings, "XAI_API_KEY", "")
    response = client.post("/chat", json={"message": "What is dog in Edo?"})
    assert response.status_code == 503
    assert response.json()["detail"] == "AI assistant is not configured"


def test_payload_enables_web_search_without_storing():
    payload = build_payload(model="grok-4.6", instructions="be helpful", message="hi", web_search=True)
    assert payload["tools"] == [{"type": "web_search"}]
    assert payload["include"] == ["no_inline_citations"]
    assert payload["store"] is False
    assert payload["instructions"] == "be helpful"
    assert payload["input"] == [{"role": "user", "content": "hi"}]


def test_payload_without_web_search_has_no_tools():
    payload = build_payload(model="grok-4.6", instructions="x", message="hi", web_search=False, temperature=0.7)
    assert "tools" not in payload
    assert "include" not in payload
    assert payload["temperature"] == 0.7


def test_parse_response_collects_text_and_unique_citations():
    data = {
        "status": "completed",
        "output": [
            {"type": "web_search_call", "status": "completed"},
            {
                "type": "message",
                "role": "assistant",
                "content": [
                    {
                        "type": "output_text",
                        "text": "Ekita means dog.",
                        "annotations": [
                            {"type": "url_citation", "url": "https://example.com/a", "title": "1"},
                            {"type": "url_citation", "url": "https://example.com/a", "title": "1"},
                            {"type": "url_citation", "url": "https://example.com/b", "title": "2"},
                        ],
                    }
                ],
            },
        ],
    }
    reply = parse_response(data)
    assert reply.text == "Ekita means dog."
    assert reply.citations == ["https://example.com/a", "https://example.com/b"]
    assert reply.used_web_search is True


def test_parse_response_without_text_raises():
    with pytest.raises(GrokError):
        parse_response({"status": "incomplete", "output": []})


def test_instructions_put_knowledge_base_first():
    instructions = main.build_instructions(
        "[KB1] Language Academy/edo-animals-dataset.json\nedo: ekita; english: dog",
        [{"name": "Linked", "url": "https://example.com", "snippet": "page text"}],
    )
    assert "Knowledge Base first, web search second" in instructions
    assert "[KB1] Language Academy/edo-animals-dataset.json" in instructions
    assert instructions.index("## Knowledge Base excerpts") < instructions.index("## Pages the user linked")


def test_instructions_without_matches_say_so():
    assert "No Knowledge Base excerpts matched" in main.build_instructions("", [])


def test_format_reply_lists_web_sources():
    assert main.format_reply(GrokReply("Answer.")) == "Answer."
    assert (
        main.format_reply(GrokReply("Answer.", ["https://example.com"]))
        == "Answer.\n\nSources:\n- https://example.com"
    )
