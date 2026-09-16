"""Summarizer registry and automatic backend selection."""

from __future__ import annotations

import logging
from collections.abc import Iterable

from .base import CompetitorDigest, Entry, Summarizer, SummarizerError
from .extractive import ExtractiveSummarizer
from .llm import (
    AnthropicSummarizer,
    GeminiSummarizer,
    GroqSummarizer,
    OllamaSummarizer,
    OpenRouterSummarizer,
)

log = logging.getLogger(__name__)

REGISTRY: dict[str, type[Summarizer]] = {
    "extractive": ExtractiveSummarizer,
    "ollama": OllamaSummarizer,
    "groq": GroqSummarizer,
    "gemini": GeminiSummarizer,
    "openrouter": OpenRouterSummarizer,
    "anthropic": AnthropicSummarizer,
}

#: Order tried by ``backend: auto``. Free-and-local first, paid never.
AUTO_ORDER = ["ollama", "groq", "gemini", "openrouter", "extractive"]


def build(name: str = "auto") -> Summarizer:
    """Return a ready summarizer.

    ``auto`` probes the free backends in :data:`AUTO_ORDER` and returns the
    first one that reports itself available; the extractive backend is the
    last entry, so this never fails and never needs a key.
    """
    name = (name or "auto").strip().lower()

    if name != "auto":
        if name not in REGISTRY:
            raise SummarizerError(
                f"unknown backend {name!r}; available: {', '.join(sorted(REGISTRY))}"
            )
        return REGISTRY[name]()

    for candidate in AUTO_ORDER:
        backend = REGISTRY[candidate]()
        if backend.available():
            log.info("auto-selected summarizer backend: %s", candidate)
            return backend

    return ExtractiveSummarizer()  # pragma: no cover - unreachable in practice


class FallbackSummarizer(Summarizer):
    """Wraps a primary backend and degrades to extractive on any failure.

    A portfolio project should not go silent because a free tier hit its
    daily quota, so a failed call downgrades that section instead of
    aborting the run.
    """

    name = "fallback"
    requires_key = False

    def __init__(self, primary: Summarizer, fallback: Summarizer | None = None) -> None:
        self.primary = primary
        self.fallback = fallback or ExtractiveSummarizer()

    @property
    def active_name(self) -> str:
        return self.primary.name

    def available(self) -> bool:
        return True

    def summarize(self, competitor: str, entries: Iterable[Entry]) -> str:
        entries = list(entries)
        try:
            text = self.primary.summarize(competitor, entries)
            if text:
                return text
            log.warning("%s returned empty output, falling back", self.primary.name)
        except SummarizerError as exc:
            log.warning("%s failed (%s), falling back to extractive", self.primary.name, exc)
        except Exception as exc:  # noqa: BLE001 - a backend must never kill the run
            log.warning("%s raised %s, falling back to extractive", self.primary.name, exc)
        return self.fallback.summarize(competitor, entries)


__all__ = [
    "AUTO_ORDER",
    "AnthropicSummarizer",
    "CompetitorDigest",
    "Entry",
    "ExtractiveSummarizer",
    "FallbackSummarizer",
    "GeminiSummarizer",
    "GroqSummarizer",
    "OllamaSummarizer",
    "OpenRouterSummarizer",
    "REGISTRY",
    "Summarizer",
    "SummarizerError",
    "build",
]
