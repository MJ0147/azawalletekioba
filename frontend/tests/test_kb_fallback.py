import importlib.util
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from services import kb_fallback

FRONTEND_DIR = Path(__file__).resolve().parents[1]
OLD_WRONG_NUMBERS = {"Ovbokhan", "Eissen", "Ihien"}


@pytest.fixture(scope="module")
def frontend():
    spec = importlib.util.spec_from_file_location("ekioba_frontend_app_fallback", FRONTEND_DIR / "app.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_snapshot_leaves_out_infrastructure_docs():
    sources = kb_fallback.get_knowledge_base().sources
    assert "Language Academy/edo-numbers-dataset.json" in sources
    assert "SECURITY.md" not in sources
    assert "DEPLOYMENT.md" not in sources
    assert not any(source.startswith("Supabase/") for source in sources)


def test_answers_vocabulary_from_the_knowledge_base():
    reply = kb_fallback.answer("What is dog in Edo?")
    assert "ekita — dog" in reply
    assert "Knowledge Base" in reply


def test_word_named_in_the_question_beats_a_longer_page():
    reply = kb_fallback.answer("What is twenty in Edo?")
    assert "ugie — twenty" in reply
    assert "twenty-one" not in reply


def test_longer_meaning_is_not_padded_with_its_parts():
    hundred = kb_fallback.answer("What is one hundred in Edo?")
    assert "iyisen — one hundred" in hundred
    assert "— one\n" not in hundred + "\n"
    seventy_five = kb_fallback.answer("seventy-five in Edo")
    assert "isèn yan ekigbesiyenen — seventy-five" in seventy_five
    assert "— seventy\n" not in seventy_five + "\n"
    assert "— five\n" not in seventy_five + "\n"


def test_numbers_come_from_the_knowledge_base_not_old_replies():
    one = kb_fallback.answer("What is one in Edo?")
    assert "owo" in one
    assert not any(word in one for word in OLD_WRONG_NUMBERS)
    assert "ikesugie" in kb_fallback.answer("How do you say fifteen in Edo?")


def test_answers_history_and_platform_questions():
    assert "Reigned only 14 days" in kb_fallback.answer("Who was Oba Ezoti?")
    pay = kb_fallback.answer("How do I pay?")
    assert "IDIA" in pay
    # Retrieval hints are hidden, including the part that wraps onto a second line.
    assert "Questions this answers" not in pay
    assert "IDIA rate, token." not in pay
    hotels = kb_fallback.answer("hotels in Lagos")
    assert "The Wheatbaker Lagos" in hotels
    assert not hotels.startswith("Port Harcourt.")


def test_unmatched_question_says_so():
    assert kb_fallback.answer("zzqx vvbnm") == kb_fallback.NO_MATCH_REPLY


def test_academy_word_list_comes_from_the_knowledge_base(frontend):
    words = kb_fallback.academy_words()
    assert {"edo": "owo", "english": "one", "category": "numbers"} in words
    assert not any(word["edo"] in OLD_WRONG_NUMBERS for word in words)
    assert len(words) == len({word["edo"] for word in words})
    assert frontend.ACADEMY_WORD_BANK == words
    assert len(frontend._build_quiz_section(size=5, category="numbers")) == 5


def test_recorded_pronunciations_attach_to_their_words(tmp_path, monkeypatch):
    (tmp_path / "ame.mp3").write_bytes(b"ID3")
    (tmp_path / "manifest.json").write_text(
        '{"amẹ": "ame.mp3", "bolo": "missing.mp3", "aro": "../escape.mp3"}', encoding="utf-8"
    )
    monkeypatch.setattr(kb_fallback, "AUDIO_DIR", tmp_path)
    kb_fallback.academy_audio.cache_clear()
    kb_fallback.academy_words.cache_clear()
    try:
        words = {word["edo"]: word for word in kb_fallback.academy_words()}
        assert words["amẹ"]["audio"] == "/static/audio/academy/ame.mp3"
        assert "audio" not in words["bolo"]  # listed, but the file doesn't exist
        assert "audio" not in words["aro"]  # paths outside the audio folder are refused
    finally:
        kb_fallback.academy_audio.cache_clear()
        kb_fallback.academy_words.cache_clear()


def test_chat_proxy_asks_grok_directly_when_no_assistant_is_deployed(frontend, monkeypatch):
    from services import stateless_answer

    monkeypatch.setattr(frontend, "NEXT_PUBLIC_IYOBO_API_URL", "")
    monkeypatch.setattr(frontend, "AI_ASSISTANT_URL", "http://localhost:8005")
    monkeypatch.setenv("XAI_API_KEY", "test-key")
    requests = []

    async def fake_create_response(*, api_key, base_url, payload, timeout):
        requests.append(payload)
        text = "Koyo! Dog in Edo is ekita."
        return {"status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": text}]}]}

    monkeypatch.setattr(stateless_answer, "create_response", fake_create_response)
    response = TestClient(frontend.app).post("/api/chat/proxy", data={"message": "What is dog in Edo?"})

    assert "Koyo! Dog in Edo is ekita." in response.text
    assert kb_fallback.OFFLINE_NOTE not in response.text
    assert "edo: ekita" in requests[0]["instructions"]  # Grok got the Knowledge Base as its main source
    assert requests[0]["tools"] == [{"type": "web_search"}]


def test_chat_proxy_falls_back_to_knowledge_base_when_ai_is_unreachable(frontend, monkeypatch):
    # A localhost AI URL is skipped, which is how the proxy behaves when no assistant is deployed,
    # and without an xAI key the website can't ask Grok itself either.
    monkeypatch.setattr(frontend, "NEXT_PUBLIC_IYOBO_API_URL", "")
    monkeypatch.setattr(frontend, "AI_ASSISTANT_URL", "http://localhost:8005")
    monkeypatch.delenv("XAI_API_KEY", raising=False)

    response = TestClient(frontend.app).post("/api/chat/proxy", data={"message": "What is dog in Edo?"})
    assert response.status_code == 200
    assert "ekita — dog" in response.text
    assert '<div class="chat-bubble bot">' in response.text
    # A visitor id cookie lets the assistant remember this person next time.
    assert len(response.cookies.get("iyobo_visitor", "")) == 32


def test_on_vercel_the_chat_uses_the_iyobo_service_on_the_same_domain(frontend, monkeypatch):
    site = "https://www.beninkingdom.online"
    monkeypatch.setattr(frontend, "NEXT_PUBLIC_IYOBO_API_URL", "")
    monkeypatch.setattr(frontend, "AI_ASSISTANT_URL", "")
    monkeypatch.setenv("VERCEL", "1")
    assert frontend._resolve_chat_url(site) == f"{site}/iyobo/chat"

    monkeypatch.delenv("VERCEL")
    assert frontend._resolve_chat_url(site) == "http://localhost:8005/chat"  # local development

    monkeypatch.setattr(frontend, "AI_ASSISTANT_URL", "https://assistant.example.com")
    assert frontend._resolve_chat_url(site) == "https://assistant.example.com/chat"  # an explicit setting wins
