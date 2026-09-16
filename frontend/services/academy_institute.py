"""
The Edo Language Academy as an institute: four graded exams built from the Knowledge Base, points for
correct answers, and IDIA Coin conversion once all four grades are passed.

Rules
- Each grade exam has 50 multiple-choice questions, marked on the server, which alone holds the
  answers. 70% passes a grade and unlocks the next one.
- A correct answer is worth 10 points, but only answers beyond your best score in that grade earn
  points, so retakes can't farm points: each grade is worth at most 500 points.
- After passing Grades 1 to 4, points convert at 100 points = 1 IDIA Coin. A conversion is a request
  the EKIOBA team reviews before sending the IDIA to the learner's signed-in TON wallet.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Optional

from services import kb_fallback
from services.academy_store import AcademyStore, ConversionPending, NotEnoughPoints
from services.knowledge_base import normalize
from services.ton import TonServiceError, normalize_address

EXAM_QUESTIONS = 50
PASS_PERCENT = 70
POINTS_PER_CORRECT = 10
POINTS_PER_IDIA = 100
CONVERSION_STATUSES = {"pending", "paid", "rejected", "all"}


class AcademyError(Exception):
    """A request the Academy refuses, with the HTTP status and the message to show."""

    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


@dataclass(frozen=True)
class Grade:
    number: int
    title: str
    description: str
    categories: tuple[str, ...]  # academy_vocabulary categories in the Knowledge Base


GRADES = (
    Grade(1, "Everyday words", "Nouns, family, food, nature, places, the body and first phrases.",
          ("noun", "family", "food", "nature", "place", "body", "phrase", "response")),
    Grade(2, "Counting in Edo", "Numbers from one to one hundred.", ("numbers",)),
    Grade(3, "Animals and actions", "Animals, verbs and the words that go with them.",
          ("animal", "verb", "adverb", "auxiliary")),
    Grade(4, "Describing and asking", "Adjectival verbs, adjectives, ideophones and question particles.",
          ("adjectival_verb", "adjective", "ideophone", "particle")),
)


def grade_for(number: Any) -> Grade:
    try:
        wanted = int(number)
    except (TypeError, ValueError):
        wanted = 0
    for grade in GRADES:
        if grade.number == wanted:
            return grade
    raise AcademyError(400, f"Choose a grade from 1 to {len(GRADES)}.")


def display_address(raw: str) -> str:
    """The wallet as people see it in their wallet app (non-bounceable, user-friendly)."""
    try:
        return normalize_address(raw, bounceable=False)
    except TonServiceError:
        return raw


# ── Exams ────────────────────────────────────────────────────────────────────


def _distractors(word: dict[str, str], field: str, pool: list[dict[str, str]], words: list[dict[str, str]], rng: random.Random) -> list[str]:
    """Three wrong options, from the same grade where possible, never another word with the same meaning or form."""
    meaning, form = normalize(word["english"]), normalize(word["edo"])
    seen = {normalize(word[field])}
    choices: list[str] = []
    for source in (pool, words):
        candidates = [w for w in source if normalize(w["english"]) != meaning and normalize(w["edo"]) != form]
        rng.shuffle(candidates)
        for candidate in candidates:
            key = normalize(candidate[field])
            if key and key not in seen:
                seen.add(key)
                choices.append(candidate[field])
                if len(choices) == 3:
                    return choices
    return choices


def _question(word: dict[str, str], direction: str, pool: list[dict[str, str]], words: list[dict[str, str]], rng: random.Random) -> dict[str, Any]:
    if direction == "edo_to_en":
        prompt, answer, field = f"What does “{word['edo']}” mean in English?", word["english"], "english"
    else:
        prompt, answer, field = f"How do you say “{word['english']}” in Edo?", word["edo"], "edo"
    texts = [answer, *_distractors(word, field, pool, words, rng)]
    rng.shuffle(texts)
    options = [{"label": label, "text": text} for label, text in zip("ABCD", texts)]
    return {
        "prompt": prompt,
        "options": options,
        "answer": answer,
        "answer_label": next(option["label"] for option in options if option["text"] == answer),
        "category": word.get("category", ""),
        # Hearing the Edo word helps when the question shows it.
        "audio": word.get("audio") if direction == "edo_to_en" else None,
    }


def build_exam(grade: Grade, words: list[dict[str, str]], size: int = EXAM_QUESTIONS, rng: Optional[random.Random] = None) -> list[dict[str, Any]]:
    """`size` questions on the grade's words, asked both Edo → English and English → Edo."""
    rng = rng or random.Random()
    pool = [w for w in words if w.get("category") in grade.categories and w.get("edo") and w.get("english")]
    if len(pool) < 4:
        raise AcademyError(503, f"Grade {grade.number} doesn't have enough Knowledge Base words yet.")
    pairs = [(word, direction) for word in pool for direction in ("edo_to_en", "en_to_edo")]
    rng.shuffle(pairs)
    questions: list[dict[str, Any]] = []
    while len(questions) < size:
        for word, direction in pairs:
            if len(questions) == size:
                break
            questions.append(_question(word, direction, pool, words, rng))
    return questions


def public_question(question: dict[str, Any], index: int, total: int) -> dict[str, Any]:
    """A question as the browser sees it: without the answer."""
    return {
        "index": index,
        "total": total,
        "prompt": question["prompt"],
        "options": question["options"],
        "category": str(question.get("category") or "").replace("_", " "),
        "audio": question.get("audio"),
    }


def _result(attempt: dict[str, Any]) -> dict[str, Any]:
    passed = attempt["status"] == "passed"
    return {
        "correct": attempt["correct"],
        "total": attempt["total"],
        "percent": round(attempt["correct"] * 100 / attempt["total"]) if attempt["total"] else 0,
        "passed": passed,
        "pass_percent": PASS_PERCENT,
        "points_awarded": attempt["points_awarded"],
        "next_grade": attempt["grade"] + 1 if passed and attempt["grade"] < len(GRADES) else None,
    }


def _attempt_view(attempt: dict[str, Any]) -> dict[str, Any]:
    view: dict[str, Any] = {
        "attempt_id": attempt["id"],
        "grade": attempt["grade"],
        "total": attempt["total"],
        "answered": attempt["current"],
    }
    if attempt["status"] == "in_progress":
        view["question"] = public_question(attempt["questions"][attempt["current"]], attempt["current"], attempt["total"])
    else:
        view["result"] = _result(attempt)
    return view


def _unlocked(grade_number: int, records: dict[int, dict[str, Any]]) -> bool:
    return grade_number == 1 or bool(records.get(grade_number - 1, {}).get("passed_at"))


async def start_exam(store: AcademyStore, wallet: str, grade_number: Any) -> dict[str, Any]:
    """Start a grade exam, or resume the one already under way."""
    grade = grade_for(grade_number)
    records = await store.grade_records(wallet)
    if not _unlocked(grade.number, records):
        raise AcademyError(403, f"Pass Grade {grade.number - 1} to unlock Grade {grade.number}.")
    attempt = await store.open_attempt(wallet, grade.number)
    if attempt is None:
        attempt = await store.create_attempt(wallet, grade.number, build_exam(grade, kb_fallback.academy_words()))
    return _attempt_view(attempt)


async def answer_question(store: AcademyStore, wallet: str, attempt_id: str, index: Any, choice: Any) -> dict[str, Any]:
    attempt = await store.get_attempt(attempt_id)
    if attempt is None or attempt["wallet"] != wallet:
        raise AcademyError(404, "That exam wasn't found.")
    if attempt["status"] != "in_progress":
        raise AcademyError(409, "This exam is already finished.")
    try:
        position = int(index)
    except (TypeError, ValueError):
        raise AcademyError(400, "Say which question you're answering.")
    if position != attempt["current"]:
        raise AcademyError(409, "That question was already answered.")

    question = attempt["questions"][position]
    label = str(choice or "").strip().upper()
    if label not in {option["label"] for option in question["options"]}:
        raise AcademyError(400, "Choose one of the options.")
    correct = label == question["answer_label"]
    updated = await store.record_answer(attempt_id, position, {"choice": label, "correct": correct}, correct)
    if updated is None:
        raise AcademyError(409, "That question was already answered.")

    response: dict[str, Any] = {
        "correct": correct,
        "correct_label": question["answer_label"],
        "correct_answer": question["answer"],
        "answered": updated["current"],
        "total": updated["total"],
    }
    if updated["current"] >= updated["total"]:
        finished = await store.finish_attempt(attempt_id, pass_percent=PASS_PERCENT, points_per_correct=POINTS_PER_CORRECT)
        response["result"] = _result(finished)
    else:
        response["next_question"] = public_question(updated["questions"][updated["current"]], updated["current"], updated["total"])
    return response


# ── The learner's record ─────────────────────────────────────────────────────


async def profile(store: AcademyStore, wallet: str) -> dict[str, Any]:
    records = await store.grade_records(wallet)
    open_attempts = await store.open_attempts(wallet)
    points = await store.points(wallet)
    conversions = await store.conversions_for(wallet)

    grades = []
    for grade in GRADES:
        record = records.get(grade.number)
        grades.append({
            "number": grade.number,
            "title": grade.title,
            "description": grade.description,
            "unlocked": _unlocked(grade.number, records),
            "passed": bool(record and record["passed_at"]),
            "best_percent": round(record["best_correct"] * 100 / record["total"]) if record and record["total"] else None,
            "attempts": record["attempts"] if record else 0,
            "in_progress": open_attempts.get(grade.number),
        })

    convertible_points = points["available"] // POINTS_PER_IDIA * POINTS_PER_IDIA
    return {
        "wallet": wallet,
        "wallet_display": display_address(wallet),
        "pass_percent": PASS_PERCENT,
        "exam_questions": EXAM_QUESTIONS,
        "grades": grades,
        "points": {**points, "per_correct": POINTS_PER_CORRECT, "max_per_grade": POINTS_PER_CORRECT * EXAM_QUESTIONS},
        "idia": {
            "points_per_idia": POINTS_PER_IDIA,
            "eligible": all(grade["passed"] for grade in grades),
            "convertible_points": convertible_points,
            "convertible_idia": convertible_points // POINTS_PER_IDIA,
            "pending_request": any(conversion["status"] == "pending" for conversion in conversions),
        },
        "conversions": conversions,
    }


async def request_conversion(store: AcademyStore, wallet: str) -> dict[str, Any]:
    records = await store.grade_records(wallet)
    if not all(records.get(grade.number, {}).get("passed_at") for grade in GRADES):
        raise AcademyError(403, f"Pass Grades 1 to {len(GRADES)} before converting points to IDIA Coin.")
    try:
        return await store.create_conversion(wallet, POINTS_PER_IDIA)
    except ConversionPending:
        raise AcademyError(409, "You already have a conversion waiting for review.")
    except NotEnoughPoints:
        raise AcademyError(400, f"You need at least {POINTS_PER_IDIA} points to convert.")


# ── Reviewing conversions (EKIOBA team) ─────────────────────────────────────


def _with_display(conversion: dict[str, Any]) -> dict[str, Any]:
    return {**conversion, "wallet_display": display_address(conversion["wallet"])}


async def list_conversions(store: AcademyStore, status: str, limit: int) -> list[dict[str, Any]]:
    if status not in CONVERSION_STATUSES:
        raise AcademyError(400, "Status must be pending, paid, rejected or all.")
    rows = await store.list_conversions(status, max(1, min(int(limit), 500)))
    return [_with_display(row) for row in rows]


async def review_conversion(store: AcademyStore, conversion_id: int, *, paid: bool, tx_hash: Any, note: Any) -> dict[str, Any]:
    tx = " ".join(str(tx_hash or "").split())
    if paid and not tx:
        raise AcademyError(400, "Add the transaction hash of the IDIA transfer.")
    if len(tx) > 128:
        raise AcademyError(400, "That transaction hash is too long.")
    row = await store.review_conversion(conversion_id, paid=paid, tx_hash=tx or None, note=str(note or "").strip()[:1000] or None)
    if row is None:
        raise AcademyError(404, "No pending conversion with that id.")
    return _with_display(row)
