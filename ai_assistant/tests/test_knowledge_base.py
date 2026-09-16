import json
from pathlib import Path

import pytest

from app.knowledge_base import KnowledgeBase, format_context, normalize, resolve_root, tokenize
from config import settings


@pytest.fixture(scope="module")
def project_kb() -> KnowledgeBase:
    root = resolve_root()
    if root is None:
        pytest.skip("Knowledge Base folder not found")
    return KnowledgeBase.load(root, exclude=settings.knowledge_base_exclude_list())


def test_normalize_strips_tone_marks_and_subdots():
    assert normalize("Ẹwẹ ọ̀kpìá") == "ewe okpia"


def test_tokenize_drops_stopwords_and_single_letters():
    assert tokenize("What is the Edo word for dog? a") == ["edo", "word", "dog"]


def test_project_knowledge_base_includes_language_academy(project_kb):
    assert "Language Academy/edo-animals-dataset.json" in project_kb.sources
    assert "Language Academy/edo-questions-grammar.md" in project_kb.sources


def test_project_knowledge_base_excludes_infrastructure_docs(project_kb):
    assert "SECURITY.md" not in project_kb.sources
    assert "DEPLOYMENT.md" not in project_kb.sources
    assert not any(source.startswith("Supabase/") for source in project_kb.sources)


def test_search_finds_vocabulary(project_kb):
    hits = project_kb.search("What is dog in Edo?", limit=3)
    assert any("ekita" in chunk.text.lower() for chunk, _ in hits)


def test_search_ignores_tone_marks(project_kb):
    hits = project_kb.search("ewe", limit=3)
    assert any("goat" in chunk.text for chunk, _ in hits)


def test_search_finds_phrase_made_of_common_words(project_kb):
    """The Knowledge Base teaches two ways to ask this, and either one answers the question.

    d'emwin comes from the everyday word list; vb' ọna khin? from the demonstratives lesson.
    """
    hits = project_kb.search("What is this?", limit=settings.KNOWLEDGE_BASE_TOP_K)
    text = " ".join(chunk.text.lower() for chunk, _ in hits)
    assert "d'emwin" in text or "ọna khin" in text


def test_phrase_match_outranks_single_word_match(tmp_path: Path):
    data = {"rows": [{"edo": "no", "english": "ask"}, {"edo": "d'emwin", "english": "what is this?"}]}
    (tmp_path / "phrases-dataset.json").write_text(json.dumps(data), encoding="utf-8")
    kb = KnowledgeBase.load(tmp_path)
    assert kb.search("how do you ask what is this")[0][0].text == "edo: d'emwin; english: what is this?"


def test_markdown_is_split_at_headings_outside_code(tmp_path: Path):
    (tmp_path / "notes.md").write_text(
        "# Title\nintro\n## Birds\nugu is vulture\n```\n# not a heading\n```\n", encoding="utf-8"
    )
    kb = KnowledgeBase.load(tmp_path)
    assert [chunk.title for chunk in kb.chunks] == ["Title", "Title > Birds"]
    assert "# not a heading" in kb.chunks[1].text


def test_json_records_become_separate_chunks(tmp_path: Path):
    data = {
        "source": {"title": "Test"},
        "rows": [{"edo": "ekita", "english": "dog"}, {"edo": "ologbo", "english": "cat"}],
    }
    (tmp_path / "vocab-dataset.json").write_text(json.dumps(data), encoding="utf-8")
    kb = KnowledgeBase.load(tmp_path)
    texts = [chunk.text for chunk in kb.chunks]
    assert "edo: ekita; english: dog" in texts
    assert "edo: ologbo; english: cat" in texts
    assert kb.search("cat")[0][0].text == "edo: ologbo; english: cat"


def test_exclude_matches_files_and_folders_case_insensitively(tmp_path: Path):
    (tmp_path / "SECURITY.md").write_text("# Secrets\nrotate keys", encoding="utf-8")
    (tmp_path / "Supabase").mkdir()
    (tmp_path / "Supabase" / "notes.md").write_text("# RLS\npolicies", encoding="utf-8")
    (tmp_path / "keep.md").write_text("# Keep\nvisible", encoding="utf-8")
    kb = KnowledgeBase.load(tmp_path, exclude=["security.md", "Supabase"])
    assert kb.sources == ["keep.md"]


def test_format_context_labels_excerpts_within_budget(tmp_path: Path):
    (tmp_path / "a.md").write_text("# One\n" + "x" * 50 + "\n# Two\n" + "y" * 50, encoding="utf-8")
    kb = KnowledgeBase.load(tmp_path)
    text, sources = format_context([(chunk, 1.0) for chunk in kb.chunks], max_chars=80)
    assert text.startswith("[KB1] a.md — One\n")
    assert "[KB2]" not in text
    assert sources == ["a.md"]


def test_missing_folder_gives_empty_index(tmp_path: Path):
    kb = KnowledgeBase.load(tmp_path / "missing")
    assert kb.chunks == []
    assert kb.search("dog") == []
