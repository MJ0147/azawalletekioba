"""
Offline answers for the site chat, drawn from the Knowledge Base.

Used only when Iyobo (the AI assistant service) can't be reached. There is no language model here,
so replies quote the best-matching Knowledge Base entries directly.

The data is a copy of the repo's "Knowledge Base" folder in frontend/knowledge_base/, and
services/knowledge_base.py is a copy of the AI assistant's search code. Both are refreshed by
scripts/sync_knowledge_base.py, because Vercel and the Docker image only ship the frontend folder.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from services.knowledge_base import Chunk, KnowledgeBase, normalize

SNAPSHOT_DIR = Path(__file__).resolve().parent.parent / "knowledge_base"

MAX_HITS = 8
MAX_VOCABULARY_LINES = 3
MAX_EXCERPT_CHARS = 700
# Further vocabulary matches are listed only if they score at least this share of the best match.
RELATED_SCORE_RATIO = 0.6

NO_MATCH_REPLY = (
    "Iyobo's AI is offline right now, and the Knowledge Base has nothing on that yet. "
    "Try asking about Edo words and numbers, the Obas of Benin, or shopping on EKIOBA."
)
OFFLINE_NOTE = "Iyobo's AI is offline, so this is quoted directly from the EKIOBA Knowledge Base"

_WORD = re.compile(r"[a-z0-9]+")
_FIELD_SPLIT = re.compile(r"; (?=[a-z_]+: )")
_FIELD = re.compile(r"^([a-z_]+): (.*)$", re.DOTALL)
_TABLE_SEPARATOR = re.compile(r"^\|?[\s:|-]*-{3,}[\s:|-]*\|?$")
_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_EMPHASIS = re.compile(r"(\*\*|\*|`)")
# Retrieval hints in the Knowledge Base ("Questions this answers: ...") aren't meant for readers.
_HINT_PREFIX = "questions this answers:"


@dataclass(frozen=True)
class _Record:
    chunk: Chunk
    score: float
    fields: dict[str, str]


# Knowledge Base categories whose names differ from the Academy page's sections.
_ACADEMY_CATEGORY_NAMES = {"number": "numbers", "greeting": "greetings", "gratitude": "greetings"}

# Pronunciation clips recorded by the project owner. manifest.json maps an Edo headword (as written
# in academy_vocabulary) to a file in this folder, e.g. {"amẹ": "ame.mp3"}.
AUDIO_DIR = Path(__file__).resolve().parent.parent / "static" / "audio" / "academy"
AUDIO_URL_PREFIX = "/static/audio/academy/"


@lru_cache(maxsize=1)
def get_knowledge_base() -> KnowledgeBase:
    return KnowledgeBase.load(SNAPSHOT_DIR)


@lru_cache(maxsize=1)
def academy_audio() -> dict[str, str]:
    """Edo headword -> URL of its pronunciation clip, for clips whose file actually exists."""
    try:
        manifest = json.loads((AUDIO_DIR / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(manifest, dict):
        return {}
    return {
        str(headword): AUDIO_URL_PREFIX + filename
        for headword, filename in manifest.items()
        if isinstance(filename, str) and "/" not in filename and "\\" not in filename
        and (AUDIO_DIR / filename).is_file()
    }


@lru_cache(maxsize=1)
def academy_words() -> list[dict[str, str]]:
    """The Academy's offline word list: every academy_vocabulary entry in the Knowledge Base copy.

    Words with a recorded pronunciation also carry an "audio" URL.
    """
    audio = academy_audio()
    words: list[dict[str, str]] = []
    seen: set[str] = set()
    for path in sorted((SNAPSHOT_DIR / "Language Academy").glob("*-dataset.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for row in data.get("academy_vocabulary", []):
            edo = str(row.get("edo") or "").strip()
            english = str(row.get("english") or "").strip()
            if not edo or not english or edo in seen:
                continue
            seen.add(edo)
            category = str(row.get("category") or "general").strip().lower()
            word = {"edo": edo, "english": english, "category": _ACADEMY_CATEGORY_NAMES.get(category, category)}
            if edo in audio:
                word["audio"] = audio[edo]
            words.append(word)
    return words


def _words(text: str) -> str:
    return " ".join(_WORD.findall(normalize(text)))


def _record_fields(text: str) -> dict[str, str] | None:
    """Parse a JSON record chunk ("edo: ekita; english: dog; ...") into fields."""
    fields: dict[str, str] = {}
    for part in _FIELD_SPLIT.split(text):
        match = _FIELD.match(part)
        if not match:
            return None
        fields[match.group(1)] = match.group(2).strip()
    return fields


def _vocabulary_records(hits: list[tuple[Chunk, float]]) -> list[_Record]:
    records = []
    for chunk, score in hits:
        fields = _record_fields(chunk.text)
        if fields and fields.get("edo") and fields.get("english"):
            records.append(_Record(chunk, score, fields))
    return records


def _vocabulary_line(fields: dict[str, str]) -> str:
    line = f"{fields['edo']} — {fields['english']}"
    if fields.get("number"):
        line = f"{fields['number']}: {line}"
    example = fields.get("example", "")
    # Examples like "ekita — dog (domestic)" only repeat the entry; keep ones that add a sentence.
    if example and not normalize(example).startswith(normalize(fields["edo"])):
        line = f"{line} (e.g. {example})"
    return line


def _vocabulary_body(records: list[_Record]) -> str:
    lines: list[str] = []
    seen: set[tuple[str, str]] = set()
    for record in records:
        key = (_words(record.fields["edo"]), _words(record.fields["english"]))
        if key in seen:
            continue
        seen.add(key)
        lines.append(f"• {_vocabulary_line(record.fields)}")
        if len(lines) == MAX_VOCABULARY_LINES:
            break
    return "\n".join(lines)


def _plain_text(markdown: str) -> str:
    lines: list[str] = []
    in_hint = False
    for raw in markdown.splitlines():
        line = raw.strip()
        if not line:
            in_hint = False  # a hint ends at the paragraph break, even if it wrapped onto more lines
            continue
        if in_hint or line.lower().startswith(_HINT_PREFIX):
            in_hint = True
            continue
        if _TABLE_SEPARATOR.match(line) or line == "---":
            continue
        if line.startswith("|"):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            line = " — ".join(cell for cell in cells if cell)
        elif line.startswith("- "):
            line = "• " + line[2:]
        line = _EMPHASIS.sub("", _LINK.sub(r"\1", line)).lstrip("#").strip()
        if line:
            lines.append(line)

    text = ""
    for line in lines:
        if len(text) + len(line) + 1 > MAX_EXCERPT_CHARS:
            return (text + "\n…").strip()
        text = f"{text}\n{line}" if text else line
    return text


def _source_label(chunk: Chunk) -> str:
    if chunk.source.lower().endswith(".md") and chunk.title:
        return chunk.title.split(" > ")[0]
    stem = Path(chunk.source).stem.replace("-dataset", "").replace("-", " ")
    return stem[:1].upper() + stem[1:]


def answer(question: str) -> str:
    """Best Knowledge Base answer to a chat message, formatted as plain text."""
    hits = get_knowledge_base().search(question, limit=MAX_HITS)
    if not hits:
        return NO_MATCH_REPLY

    top, top_score = hits[0]
    records = _vocabulary_records(hits)
    question_words = f" {_words(question)} "

    # A word whose English meaning is spelled out in the question ("What is twenty in Edo?") is the
    # answer, even when a longer page mentions that English word more often.
    exact = [r for r in records if f" {_words(r.fields['english'])} " in question_words]
    # Keep the longest meanings: "one hundred" shouldn't also list "one", nor "seventy-five" list "five".
    exact.sort(key=lambda r: -len(_words(r.fields["english"]).split()))
    longest: list[_Record] = []
    for record in exact:
        phrase = f" {_words(record.fields['english'])} "
        if not any(phrase in f" {_words(kept.fields['english'])} " for kept in longest if kept.fields["english"] != record.fields["english"]):
            longest.append(record)
    exact = longest
    if exact:
        body, source = _vocabulary_body(exact), exact[0].chunk
    elif records and records[0].chunk is top:
        related = [r for r in records if r.score >= top_score * RELATED_SCORE_RATIO]
        body, source = _vocabulary_body(related), top
    else:
        heading = top.title.split(" > ")[-1] if top.title else ""
        excerpt = _plain_text(top.text)
        body = f"{heading}\n{excerpt}" if heading and heading not in excerpt else excerpt
        source = top

    return f"{body}\n\n({OFFLINE_NOTE}: {_source_label(source)}.)"
