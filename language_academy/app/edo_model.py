from __future__ import annotations

import json
import random
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
        self.english_to_edo = {item.english.lower(): item.edo for item in self.words}
        self.edo_to_english = {item.edo.lower(): item.english for item in self.words}

    def _load_words(self) -> list[EdoWord]:
        with self.data_path.open("r", encoding="utf-8") as file:
            raw_items = json.load(file)
        return [EdoWord(**item) for item in raw_items]

    def _load_context_items(self) -> list[EdoContextItem]:
        return [
            EdoContextItem(
                pattern="noun_phrase",
                edo="owa",
                translation="house",
                note="A simple noun example from Edo vocabulary context.",
                tags=["vocabulary", "noun", "context-a"],
            ),
            EdoContextItem(
                pattern="question_with_yi",
                edo="Osaro gha rre yi?",
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
                edo="Osaro bo owa ra Osaro rhie okhuo?",
                translation="Did Osaro build a house or marry a woman?",
                note="ra coordinates alternatives and marks the resulting question.",
                tags=["grammar", "ra", "alternative-question"],
            ),
            EdoContextItem(
                pattern="ra_short_polar",
                edo="Osaro bo owa ra?",
                translation="Did Osaro build a house?",
                note="Sentence-final ra can function as a question marker in reduced alternatives.",
                tags=["grammar", "ra", "polar-question"],
            ),
            EdoContextItem(
                pattern="de_np_question",
                edo="De ehe ne Osaro tie yi?",
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

    def translate(self, phrase: str, direction: str) -> str:
        tokens = phrase.lower().split()
        if direction == "en_to_edo":
            translated = [self.english_to_edo.get(token, f"[{token}]") for token in tokens]
        else:
            translated = [self.edo_to_english.get(token, f"[{token}]") for token in tokens]
        return " ".join(translated)

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
            normalized = query.strip().lower()
            items = [
                item
                for item in items
                if normalized in item.pattern.lower()
                or normalized in item.edo.lower()
                or normalized in item.translation.lower()
                or normalized in item.note.lower()
                or any(normalized in tag.lower() for tag in item.tags)
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
        normalized = particle.strip().lower()
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
        normalized_query = query.strip().lower()
        if not normalized_query:
            return []

        results: list[EdoWord] = []
        for item in self.words:
            targets = {
                "edo": item.edo.lower(),
                "english": item.english.lower(),
                "example": item.example.lower(),
                "category": item.category.lower(),
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
        options = [answer.english, *distractors[:3]]
        random.shuffle(options)
        return {
            "prompt": f"What is the meaning of '{answer.edo}'?",
            "answer": answer.english,
            "options": options,
        }
