from __future__ import annotations

import json
import random
import unicodedata
from dataclasses import dataclass
from pathlib import Path


@dataclass
class EdoWord:
    edo: str
    english: str
    category: str
    example: str


@dataclass
class EdoContextItem:
    pattern: str
    edo: str
    translation: str
    note: str
    tags: list[str]


class EdoLanguageModel:
    def __init__(self, data_path: Path) -> None:
        self.data_path = data_path
        self.words = self._load_words()
        self.context_items = self._load_context_items()
        self.english_to_edo = {
            self._normalize_text(item.english): item.edo
            for item in self.words
        }
        self.edo_to_english = {
            self._normalize_text(item.edo): item.english
            for item in self.words
        }

    def _load_words(self) -> list[EdoWord]:
        with self.data_path.open("r", encoding="utf-8") as file:
            raw_items = json.load(file)
        return [EdoWord(**item) for item in raw_items]

    def _load_context_items(self) -> list[EdoContextItem]:
        return [
            EdoContextItem(
                pattern="noun_phrase",
                edo="owä",
                translation="house",
                note="A simple noun example from Edo vocabulary context.",
                tags=["vocabulary", "noun", "context-a"],
            ),
            EdoContextItem(
                pattern="question_with_yi",
                edo="Osaro ghä rre yi?",
                translation="Will Osaro come?",
                note="Sentence-final yi marks a polar question in this context.",
                tags=["grammar", "yi", "polar-question"],
            ),
            EdoContextItem(
                pattern="statement",
                edo="Osaro rri evbare.",
                translation="Osaro is eating.",
                note="Progressive-like statement used as contrast with question forms.",
                tags=["grammar", "statement", "verb"],
            ),
            EdoContextItem(
                pattern="negative_with_yi",
                edo="U ma rhie okhuo yi.",
                translation="You have not married a woman before.",
                note="In negative contexts, yi can carry a temporal meaning like 'before'.",
                tags=["grammar", "yi", "negative", "temporal"],
            ),
            EdoContextItem(
                pattern="focus_with_yi",
                edo="Evbare ere Osaro re yi?",
                translation="Is it food that Osaro is eating?",
                note="yi combines question force with emphasis in focus constructions.",
                tags=["grammar", "yi", "focus", "emphasis"],
            ),
            EdoContextItem(
                pattern="alternative_question_ra",
                edo="Ösaro bo owä ra Ösärorhie bkhub?",
                translation="Did Osaro build a house or marry a woman?",
                note="ra coordinates alternatives and marks the resulting question.",
                tags=["grammar", "ra", "alternative-question"],
            ),
            EdoContextItem(
                pattern="ra_short_polar",
                edo="Osaro bo owä ra?",
                translation="Did Osaro build a house?",
                note="Sentence-final ra can function as a question marker in reduced alternatives.",
                tags=["grammar", "ra", "polar-question"],
            ),
            EdoContextItem(
                pattern="de_np_question",
                edo="De ehe ne Ösäro tie (yi)?",
                translation="Which book is Osaro reading?",
                note="de introduces non-polar questions about a noun phrase.",
                tags=["grammar", "de", "non-polar", "question-word"],
            ),
        ]

    def train_summary(self) -> dict[str, int | str]:
        categories = {item.category for item in self.words}
        return {
            "model": "edo-vocab-baseline-v1",
            "vocab_size": len(self.words),
            "categories": len(categories),
        }

    @staticmethod
    def _strip_diacritics(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value)
        return "".join(ch for ch in normalized if not unicodedata.combining(ch))

    @classmethod
    def _normalize_text(cls, value: str) -> str:
        lowered = value.strip().lower()
        lowered = cls._strip_diacritics(lowered)
        lowered = " ".join(lowered.split())
        legacy_map = {
            "owa": "owa",
            "gha": "gha",
            "okhuo": "okhuo",
        }
        tokens = [legacy_map.get(token, token) for token in lowered.split()]
        return " ".join(tokens)

    def _translate_phrase(self, phrase: str, mapping: dict[str, str]) -> str:
        tokens = phrase.split()
        if not tokens:
            return ""

        translated: list[str] = []
        i = 0
        max_window = 4
        while i < len(tokens):
            matched = False
            for window in range(min(max_window, len(tokens) - i), 0, -1):
                segment = " ".join(tokens[i : i + window])
                key = self._normalize_text(segment)
                if key in mapping:
                    translated.append(mapping[key])
                    i += window
                    matched = True
                    break
            if not matched:
                translated.append(f"[{tokens[i]}]")
                i += 1

        return " ".join(translated)

    def translate(self, phrase: str, direction: str) -> str:
        if direction == "en_to_edo":
            return self._translate_phrase(phrase, self.english_to_edo)
        return self._translate_phrase(phrase, self.edo_to_english)

    def vocabulary(self, category: str | None = None, limit: int = 10) -> list[dict[str, str]]:
        pool = self.words
        if category:
            pool = [item for item in pool if item.category == category]
        items = pool[: max(1, limit)]
        return [
            {
                "edo": item.edo,
                "english": item.english,
                "category": item.category,
                "example": item.example,
            }
            for item in items
        ]

    def categories(self) -> list[str]:
        return sorted({item.category for item in self.words})

    def category_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for word in self.words:
            counts[word.category] = counts.get(word.category, 0) + 1
        return counts

    def vocabulary_context(self, query: str | None = None, limit: int = 10) -> list[dict[str, str | list[str]]]:
        items = self.context_items
        if query:
            normalized = self._normalize_text(query)
            items = [
                item
                for item in items
                if normalized in self._normalize_text(item.pattern)
                or normalized in self._normalize_text(item.edo)
                or normalized in self._normalize_text(item.translation)
                or normalized in self._normalize_text(item.note)
                or any(normalized in self._normalize_text(tag) for tag in item.tags)
            ]

        return [
            {
                "pattern": item.pattern,
                "edo": item.edo,
                "translation": item.translation,
                "note": item.note,
                "tags": item.tags,
            }
            for item in items[: max(1, limit)]
        ]

    def particle_functions(self, particle: str) -> dict[str, object]:
        normalized = self._normalize_text(particle)
        particle_map: dict[str, dict[str, object]] = {
            "yi": {
                "particle": "yi",
                "functions": [
                    "sentence-final polar question marker",
                    "temporal adverbial meaning in some negative constructions",
                    "emphasis marker in focus constructions",
                ],
            },
            "ra": {
                "particle": "ra",
                "functions": [
                    "coordinator linking alternatives",
                    "question marker in alternative or reduced alternative questions",
                ],
            },
            "de": {
                "particle": "de",
                "functions": [
                    "question particle introducing non-polar noun phrase questions",
                    "focus marker for the questioned constituent",
                ],
            },
        }

        base = particle_map.get(
            normalized,
            {
                "particle": normalized,
                "functions": [],
                "note": "No curated Edo grammar function found for this particle.",
            },
        )
        base["examples"] = self.vocabulary_context(query=normalized, limit=5)
        return base

    def search(self, query: str, field: str = "any", limit: int = 10) -> list[dict[str, str]]:
        normalized_query = self._normalize_text(query)
        if not normalized_query:
            return []

        results: list[EdoWord] = []
        for item in self.words:
            targets = {
                "edo": self._normalize_text(item.edo),
                "english": self._normalize_text(item.english),
                "example": self._normalize_text(item.example),
                "category": self._normalize_text(item.category),
            }

            if field == "any":
                if any(normalized_query in value for value in targets.values()):
                    results.append(item)
            elif field in targets and normalized_query in targets[field]:
                results.append(item)

        return [
            {
                "edo": item.edo,
                "english": item.english,
                "category": item.category,
                "example": item.example,
            }
            for item in results[: max(1, limit)]
        ]

    def daily_lesson(self, size: int = 3, category: str | None = None) -> dict[str, object]:
        pool = self.words
        if category:
            pool = [item for item in self.words if item.category == category]

        if not pool:
            return {"category": category, "items": [], "count": 0}

        lesson_size = max(1, min(size, len(pool)))
        selected = random.sample(pool, k=lesson_size)
        items = [
            {
                "edo": item.edo,
                "english": item.english,
                "category": item.category,
                "example": item.example,
            }
            for item in selected
        ]
        return {"category": category, "items": items, "count": len(items)}

    def quiz_question(self, category: str | None = None) -> dict[str, str | list[str]]:
        pool = self.words
        if category:
            pool = [item for item in self.words if item.category == category]
        if not pool:
            pool = self.words

        answer = random.choice(pool)
        distractors = [word.english for word in self.words if word.english != answer.english]
        random.shuffle(distractors)
        options = [answer.english, *distractors[:2]]
        random.shuffle(options)
        labels = ["A", "B", "C"]
        labeled_options = [
            {"label": labels[i], "text": option}
            for i, option in enumerate(options)
        ]
        answer_label = next((opt["label"] for opt in labeled_options if opt["text"] == answer.english), "A")
        return {
            "prompt": f"What is the meaning of '{answer.edo}'?",
            "answer": answer.english,
            "answer_label": answer_label,
            "options": labeled_options,
        }

    def quiz_section(self, size: int = 50, category: str | None = None) -> dict[str, object]:
        question_count = max(1, min(size, 50))
        questions = [self.quiz_question(category=category) for _ in range(question_count)]
        return {
            "category": category or "general",
            "count": len(questions),
            "questions": questions,
        }
