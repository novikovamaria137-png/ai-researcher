"""The summarization layer: extractive quality, registry, and fallback behaviour."""

import pytest

from ai_researcher import summarizers
from ai_researcher.summarizers import (
    ExtractiveSummarizer,
    FallbackSummarizer,
    SummarizerError,
)
from ai_researcher.summarizers.base import Summarizer
from ai_researcher.summarizers.extractive import split_sentences, summarize_text


def test_extractive_needs_no_key_and_is_always_available():
    backend = ExtractiveSummarizer()
    assert backend.available() is True
    assert backend.requires_key is False


def test_extractive_produces_bullets_with_links(entries):
    output = ExtractiveSummarizer().summarize("Competitor A", entries)
    assert output.count("•") >= 2
    assert "https://example.com/a1" in output
    assert "Ключевые темы" in output


def test_extractive_handles_empty_input():
    assert ExtractiveSummarizer().summarize("Nobody", []) == ""


def test_summarize_text_keeps_source_order_and_limit():
    text = (
        "The company launched a new product today. "
        "It costs forty nine dollars per seat every month. "
        "An unrelated sentence about the weather in Amsterdam appears here. "
        "The beta opens to enterprise customers next month worldwide."
    )
    picked = summarize_text(text, max_sentences=2)
    assert len(picked) == 2
    assert picked == [s for s in split_sentences(text) if s in picked]


def test_split_sentences_drops_fragments():
    assert split_sentences("Ok. ") == []


def test_build_auto_never_raises_and_returns_a_working_backend(monkeypatch):
    # No keys in the environment -> auto must land on extractive.
    for key in ("GROQ_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(
        summarizers.OllamaSummarizer, "available", lambda self: False
    )
    backend = summarizers.build("auto")
    assert backend.name == "extractive"


def test_build_rejects_unknown_backend():
    with pytest.raises(SummarizerError):
        summarizers.build("gpt-9000")


def test_build_named_backend():
    assert summarizers.build("groq").name == "groq"


def test_auto_order_never_selects_a_paid_backend():
    assert "anthropic" not in summarizers.AUTO_ORDER
    assert summarizers.AUTO_ORDER[-1] == "extractive"


class _Broken(Summarizer):
    name = "broken"

    def available(self):
        return True

    def summarize(self, competitor, entries):
        raise SummarizerError("quota exceeded")


class _Empty(Summarizer):
    name = "empty"

    def available(self):
        return True

    def summarize(self, competitor, entries):
        return ""


@pytest.mark.parametrize("primary", [_Broken(), _Empty()])
def test_fallback_degrades_instead_of_crashing(primary, entries):
    engine = FallbackSummarizer(primary)
    output = engine.summarize("Competitor A", entries)
    assert "•" in output  # extractive output, run completed


def test_prompt_contains_competitor_and_entries(entries):
    prompt = ExtractiveSummarizer().build_prompt("Competitor A", entries)
    assert "Competitor A" in prompt
    assert "enterprise support" in prompt
