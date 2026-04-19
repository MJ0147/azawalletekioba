from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_train_returns_summary() -> None:
    response = client.post("/train")
    assert response.status_code == 200
    payload = response.json()
    assert payload["model"] == "edo-vocab-baseline-v1"
    assert payload["vocab_size"] >= 5


def test_quiz_question_has_options() -> None:
    response = client.get("/quiz/question")
    assert response.status_code == 200
    payload = response.json()
    assert "prompt" in payload
    assert len(payload["options"]) == 4


def test_translate_en_to_edo() -> None:
    response = client.post("/translate", json={"text": "hello", "direction": "en_to_edo"})
    assert response.status_code == 200
    assert "translated_text" in response.json()


def test_vocabulary_categories_returns_counts() -> None:
    response = client.get("/vocabulary/categories")
    assert response.status_code == 200
    payload = response.json()
    assert "categories" in payload
    assert "counts" in payload
    assert "noun" in payload["categories"]


def test_vocabulary_search_returns_matches() -> None:
    response = client.get("/vocabulary/search", params={"query": "hello", "field": "english"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["field"] == "english"
    assert len(payload["items"]) >= 1


def test_lesson_daily_returns_items() -> None:
    response = client.get("/lesson/daily", params={"size": 2})
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 2
    assert len(payload["items"]) == 2


def test_translate_batch() -> None:
    response = client.post(
        "/translate/batch",
        json={"texts": ["hello", "water"], "direction": "en_to_edo"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["direction"] == "en_to_edo"
    assert len(payload["results"]) == 2


def test_vocabulary_context_filters_by_particle() -> None:
    response = client.get("/vocabulary/context", params={"query": "yi"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "yi"
    assert len(payload["items"]) >= 1
    assert any("yi" in " ".join(item["tags"]).lower() for item in payload["items"])


def test_grammar_particle_returns_examples() -> None:
    response = client.get("/grammar/particle/ra")
    assert response.status_code == 200
    payload = response.json()
    assert payload["particle"] == "ra"
    assert len(payload["functions"]) >= 1
    assert len(payload["examples"]) >= 1


def test_quiz_answer_awards_tokens_for_correct_answer() -> None:
    response = client.post(
        "/quiz/answer",
        json={"answer": "house", "expected": "house", "user_id": "student_award"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["correct"] is True
    assert payload["awarded_tokens"] == 10
    assert payload["awarded_by"] == "ai assistant"
    assert payload["token_balance"] == 10


def test_quiz_points_balance_reflects_awards() -> None:
    response = client.post(
        "/quiz/answer",
        json={"answer": "water", "expected": "water", "user_id": "student_balance"},
    )
    assert response.status_code == 200

    points_response = client.get("/quiz/points/student_balance")
    assert points_response.status_code == 200
    points_payload = points_response.json()
    assert points_payload["token_balance"] == 10
    assert points_payload["awarded_by"] == "ai assistant"


def test_quiz_answer_wrong_does_not_award_tokens() -> None:
    response = client.post(
        "/quiz/answer",
        json={"answer": "house", "expected": "water", "user_id": "student_no_award"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["correct"] is False
    assert payload["awarded_tokens"] == 0
    assert payload["token_balance"] == 0
