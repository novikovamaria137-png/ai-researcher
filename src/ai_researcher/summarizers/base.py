"""Shared types and the abstract summarizer contract."""

from __future__ import annotations

import abc
from collections.abc import Iterable
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Entry:
    """One publication found in a competitor's feed."""

    uid: str
    title: str
    link: str
    summary: str = ""
    published: str = ""
    source: str = ""

    def as_prompt_block(self) -> str:
        head = f"## {self.title}"
        if self.published:
            head += f" ({self.published})"
        return f"{head}\n{self.summary}\n{self.link}".strip()


@dataclass
class CompetitorDigest:
    """Digest section for a single competitor."""

    competitor: str
    body: str
    entries: list[Entry] = field(default_factory=list)


PROMPT_TEMPLATE = """Конкурент: {competitor}

Новые публикации:
{text}

Сделай дайджест (3–5 буллетов):
- Что нового (продукт / фича / партнёрство / маркетинговый ход)?
- Что это значит для нас?
- Опасно / нейтрально / возможность.

Только важное. Прямо, без воды. Без вступлений и заключений."""


class Summarizer(abc.ABC):
    """A pluggable summarization backend.

    Implementations must be safe to construct even when their backend is
    unreachable; `available()` is what decides whether they get used.
    """

    name: str = "base"
    requires_key: bool = True

    @abc.abstractmethod
    def available(self) -> bool:
        """True when this backend can actually run right now."""

    @abc.abstractmethod
    def summarize(self, competitor: str, entries: Iterable[Entry]) -> str:
        """Return a Markdown bullet block for one competitor."""

    def build_prompt(self, competitor: str, entries: Iterable[Entry]) -> str:
        text = "\n\n".join(entry.as_prompt_block() for entry in entries)
        return PROMPT_TEMPLATE.format(competitor=competitor, text=text)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<{type(self).__name__} name={self.name!r}>"


class SummarizerError(RuntimeError):
    """Raised when a backend fails and the caller should fall back."""
