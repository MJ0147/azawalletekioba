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


def test_instructions_put_ekiobas_own_material_first():
    instructions = main.build_instructions(
        "[KB1] Language Academy/edo-animals-dataset.json\nedo: ekita; english: dog",
        [{"name": "Linked", "url": "https://example.com", "snippet": "page text"}],
    )
    assert "What you know, and how you judge what you find" in instructions
    assert "[KB1] Language Academy/edo-animals-dataset.json" in instructions
    assert instructions.index("## Reference material") < instructions.index("## Pages the user linked")


def test_instructions_forbid_naming_the_reference_material_to_the_person():
    instructions = main.build_instructions("[KB1] edo: ekita; english: dog", [])
    assert "Never expose your plumbing" in instructions
    assert "Never name it, quote its file names or show its [KB] labels." in instructions


def test_instructions_without_matches_say_so():
    assert "Nothing in EKIOBA's verified material matches" in main.build_instructions("", [])


def test_format_reply_lists_web_sources():
    assert main.format_reply(GrokReply("Answer.")) == "Answer."
    assert (
        main.format_reply(GrokReply("Answer.", ["https://example.com"]))
        == "Answer.\n\nSources:\n- https://example.com"
    )


def test_format_reply_takes_out_citations_of_the_reference_material():
    """The person hears the answer, never how it was assembled."""
    reply = GrokReply(
        "Alphabet notes (Knowledge Base: edo-alphabet-and-numbers.md):\n"
        "In Edo, dog is ekita [KB2]. I remember your name (Knowledge Base: platform-guide.md)."
    )
    assert main.format_reply(reply) == (
        "Alphabet notes:\nIn Edo, dog is ekita. I remember your name."
    )


def test_format_reply_rewrites_the_reference_material_named_mid_sentence():
    text = main.format_reply(GrokReply("The Knowledge Base flags that spelling as uncertain."))
    assert "Knowledge Base" not in text
    assert text == "EKIOBA's own material flags that spelling as uncertain."


def test_format_reply_leaves_an_ordinary_answer_alone():
    assert main.format_reply(GrokReply("Koyo! In Edo, dog is ekita.")) == "Koyo! In Edo, dog is ekita."
