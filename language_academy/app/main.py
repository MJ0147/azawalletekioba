from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.edo_model import EdoLanguageModel
from app.trainer import train_model

app = FastAPI(title="Language Academy Service")
model = EdoLanguageModel(Path(__file__).resolve().parent / "data" / "edo_vocab.json")
QUIZ_TOKEN_REWARD = 10
QUIZ_REWARD_ISSUER = "ai assistant"
USER_TOKEN_POINTS: dict[str, int] = {}

EDO_GRAMMAR_REFERENCE = {
    "polar_questions": {
        "pitch_rule": "Declarative statements can become polar questions when sentence pitch is raised.",
        "yi_particle": "The particle 'yi' can appear sentence-finally as a question marker.",
        "example": {
            "declarative": "Osaro gha rre.",
            "question": "Osaro gha rre yi?",
            "translation": "Will Osaro come?",
        },
    },
    "alternative_questions": {
        "marker": "ra",
        "description": "The conjunction/question marker 'ra' links alternatives and yields a question reading.",
        "example": {
            "edo": "Osaro bo owa ra Osaro rhie?",
            "translation": "Did Osaro build a house or marry a woman?",
        },
    },
    "focus_notes": {
        "summary": "In focus constructions, yi may add emphasis in addition to question force.",
        "note": "Sentence-final yi can be question marker, emphatic marker, or temporal adverb by context.",
    },
}


class AnalyzeRequest(BaseModel):
    text: str = Field(min_length=1)


class TranslateRequest(BaseModel):
    text: str = Field(min_length=1)
    direction: str = Field(default="en_to_edo")


class QuizAnswerRequest(BaseModel):
    answer: str = Field(min_length=1)
    expected: str = Field(min_length=1)
    user_id: str = Field(default="guest", min_length=1)


class BatchTranslateRequest(BaseModel):
    texts: list[str] = Field(min_length=1)
    direction: str = Field(default="en_to_edo")


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "language_academy"}


@app.post("/analyze")
def analyze(payload: AnalyzeRequest) -> dict[str, int | str]:
    words = payload.text.split()
    word_count = len(words)
    
    if word_count < 5:
        level = "novice"
    elif word_count < 20:
        level = "beginner"
    else:
        level = "intermediate"

    return {
        "model": "baseline-v1",
        "word_count": word_count,
        "classification": level,
    }


@app.post("/train")
def train() -> dict[str, int | str]:
    return train_model()


@app.get("/vocabulary")
def vocabulary(category: str | None = None, limit: int = 10) -> dict[str, object]:
    return {"items": model.vocabulary(category=category, limit=limit)}


@app.get("/vocabulary/categories")
def vocabulary_categories() -> dict[str, object]:
    return {
        "categories": model.categories(),
        "counts": model.category_counts(),
    }


@app.get("/vocabulary/search")
def vocabulary_search(query: str, field: str = "any", limit: int = 10) -> dict[str, object]:
    allowed_fields = {"any", "edo", "english", "example", "category"}
    if field not in allowed_fields:
        raise HTTPException(status_code=400, detail="Field must be one of any, edo, english, example, category")
    return {
        "query": query,
        "field": field,
        "items": model.search(query=query, field=field, limit=limit),
    }


@app.get("/vocabulary/context")
def vocabulary_context(query: str | None = None, limit: int = 10) -> dict[str, object]:
    return {
        "query": query,
        "items": model.vocabulary_context(query=query, limit=limit),
    }


@app.post("/translate")
def translate(payload: TranslateRequest) -> dict[str, str]:
    direction = payload.direction.lower()
    if direction not in {"en_to_edo", "edo_to_en"}:
        raise HTTPException(status_code=400, detail="Direction must be 'en_to_edo' or 'edo_to_en'")
    translated = model.translate(payload.text, direction)
    return {"direction": direction, "translated_text": translated}


@app.post("/translate/batch")
def translate_batch(payload: BatchTranslateRequest) -> dict[str, object]:
    direction = payload.direction.lower()
    if direction not in {"en_to_edo", "edo_to_en"}:
        raise HTTPException(status_code=400, detail="Direction must be 'en_to_edo' or 'edo_to_en'")
    translations = [
        {"input": text, "translated": model.translate(text, direction)}
        for text in payload.texts
    ]
    return {"direction": direction, "results": translations}


@app.get("/quiz/question")
def quiz_question(category: str | None = None) -> dict[str, str | list[str]]:
    return model.quiz_question(category=category)


@app.post("/quiz/answer")
def quiz_answer(payload: QuizAnswerRequest) -> dict[str, object]:
    is_correct = payload.answer.strip().lower() == payload.expected.strip().lower()
    user_id = payload.user_id.strip().lower()
    awarded_tokens = QUIZ_TOKEN_REWARD if is_correct else 0
    USER_TOKEN_POINTS[user_id] = USER_TOKEN_POINTS.get(user_id, 0) + awarded_tokens
    return {
        "correct": is_correct,
        "expected": payload.expected,
        "awarded_tokens": awarded_tokens,
        "awarded_by": QUIZ_REWARD_ISSUER,
        "user_id": user_id,
        "token_balance": USER_TOKEN_POINTS[user_id],
    }


@app.get("/quiz/points/{user_id}")
def quiz_points(user_id: str) -> dict[str, object]:
    normalized_user = user_id.strip().lower()
    return {
        "user_id": normalized_user,
        "token_balance": USER_TOKEN_POINTS.get(normalized_user, 0),
        "awarded_by": QUIZ_REWARD_ISSUER,
    }


@app.get("/grammar/reference")
def grammar_reference() -> dict[str, object]:
    return EDO_GRAMMAR_REFERENCE


@app.get("/grammar/particle/{particle}")
def grammar_particle(particle: str) -> dict[str, object]:
    return model.particle_functions(particle=particle)


@app.get("/lesson/daily")
def lesson_daily(size: int = 3, category: str | None = None) -> dict[str, object]:
    if size < 1:
        raise HTTPException(status_code=400, detail="Size must be at least 1")
    return model.daily_lesson(size=size, category=category)
