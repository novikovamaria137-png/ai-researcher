"""Extractive summarizer — zero dependencies, zero API keys, works offline.

Implements a lightweight TextRank-style ranking:
  1. split text into sentences (RU + EN aware);
  2. score each sentence by TF-IDF weight of its terms, normalised by length;
  3. boost leading sentences (news leads carry the facts);
  4. return the top-k sentences in original order.

This is the default backend: it guarantees the project runs for anyone who
clones it, with no account, no key and no network beyond the RSS feeds.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Iterable

from .base import Entry, Summarizer

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])\s+(?=[A-ZА-ЯЁ0-9«\"'])")
_WORD = re.compile(r"[а-яёa-z0-9][а-яёa-z0-9\-]+", re.IGNORECASE)

# Deliberately small, hand-written stop lists: no NLTK download at runtime.
_STOPWORDS = {
    # Russian
    "и", "в", "во", "не", "что", "он", "на", "я", "с", "со", "как", "а", "то",
    "все", "она", "так", "его", "но", "да", "ты", "к", "у", "же", "вы", "за",
    "бы", "по", "только", "ее", "мне", "было", "вот", "от", "меня", "еще",
    "нет", "о", "из", "ему", "теперь", "когда", "даже", "ну", "вдруг", "ли",
    "если", "уже", "или", "ни", "быть", "был", "него", "до", "вас", "нибудь",
    "опять", "уж", "вам", "ведь", "там", "потом", "себя", "ничего", "ей",
    "может", "они", "тут", "где", "есть", "надо", "ней", "для", "мы", "тебя",
    "их", "чем", "была", "сам", "чтоб", "без", "будто", "чего", "раз", "тоже",
    "себе", "под", "будет", "ж", "тогда", "кто", "этот", "того", "потому",
    "этого", "какой", "совсем", "ним", "здесь", "этом", "один", "почти",
    "мой", "тем", "чтобы", "нее", "были", "куда", "зачем", "всех", "никогда",
    "можно", "при", "наконец", "два", "об", "другой", "хоть", "после", "над",
    "больше", "тот", "через", "эти", "нас", "про", "всего", "них", "какая",
    "много", "разве", "три", "эту", "моя", "впрочем", "свою", "этой", "перед",
    "иногда", "лучше", "чуть", "том", "нельзя", "такой", "им", "более",
    "всегда", "конечно", "всю", "между",
    # English
    "the", "and", "for", "are", "but", "not", "you", "all", "any", "can",
    "her", "was", "one", "our", "out", "day", "get", "has", "him", "his",
    "how", "its", "new", "now", "old", "see", "two", "way", "who", "boy",
    "did", "use", "with", "that", "this", "from", "they", "have", "been",
    "will", "into", "your", "them", "than", "then", "were", "said", "each",
    "which", "their", "would", "there", "could", "other", "about", "after",
    "first", "also", "more", "some", "such", "only", "over", "most", "made",
    "when", "what", "where", "these", "those", "being", "because",
}

_SIGNAL_TERMS = {
    "launch", "launches", "launched", "release", "released", "announce",
    "announces", "announced", "partnership", "acquire", "acquisition",
    "funding", "raises", "raised", "pricing", "price", "hiring", "expands",
    "запуск", "запустил", "запустила", "релиз", "выпустил", "анонс",
    "партнёрство", "партнерство", "сделка", "инвестиции", "раунд", "цена",
    "подорожал", "коллаборация", "коллекция", "открытие", "открыл",
}


def split_sentences(text: str) -> list[str]:
    """Split text into sentences, tolerating messy RSS HTML remnants."""
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    parts = [s.strip() for s in _SENTENCE_SPLIT.split(text)]
    return [s for s in parts if len(s) > 25]


def tokenize(text: str) -> list[str]:
    return [w.lower() for w in _WORD.findall(text) if w.lower() not in _STOPWORDS]


def _idf(documents: list[list[str]]) -> dict[str, float]:
    n = len(documents) or 1
    df: Counter[str] = Counter()
    for doc in documents:
        df.update(set(doc))
    return {term: math.log(1 + n / (1 + count)) for term, count in df.items()}


def summarize_text(text: str, max_sentences: int = 3) -> list[str]:
    """Return up to `max_sentences` representative sentences, in source order."""
    sentences = split_sentences(text)
    if not sentences:
        return []
    if len(sentences) <= max_sentences:
        return sentences

    tokenized = [tokenize(s) for s in sentences]
    idf = _idf(tokenized)
    scores: list[tuple[int, float]] = []
    for index, tokens in enumerate(tokenized):
        if not tokens:
            scores.append((index, 0.0))
            continue
        tf = Counter(tokens)
        weight = sum((count / len(tokens)) * idf.get(term, 0.0) for term, count in tf.items())
        # Position prior: the lead of a news item carries the news.
        weight *= 1.0 + 0.35 / (1 + index)
        # Signal boost: sentences naming a concrete business event.
        if any(term in _SIGNAL_TERMS for term in tokens):
            weight *= 1.25
        scores.append((index, weight))

    best = sorted(scores, key=lambda pair: pair[1], reverse=True)[:max_sentences]
    return [sentences[index] for index, _ in sorted(best)]


def keywords(text: str, limit: int = 6) -> list[str]:
    tokens = [t for t in tokenize(text) if len(t) > 3]
    if not tokens:
        return []
    return [term for term, _ in Counter(tokens).most_common(limit)]


class ExtractiveSummarizer(Summarizer):
    """Default backend. No key, no network, no model download."""

    name = "extractive"
    requires_key = False

    def __init__(self, max_bullets: int = 4) -> None:
        self.max_bullets = max_bullets

    def available(self) -> bool:  # always
        return True

    def summarize(self, competitor: str, entries: Iterable[Entry]) -> str:
        entries = list(entries)
        if not entries:
            return ""

        bullets: list[str] = []
        for entry in entries[: self.max_bullets]:
            body = f"{entry.title}. {entry.summary}".strip()
            picked = summarize_text(body, max_sentences=2)
            line = " ".join(picked) if picked else entry.title
            line = line.strip()
            if len(line) > 320:
                line = line[:317].rsplit(" ", 1)[0] + "…"
            bullets.append(f"• {line}\n  {entry.link}")

        terms = keywords(" ".join(f"{e.title} {e.summary}" for e in entries))
        if terms:
            bullets.append("• Ключевые темы: " + ", ".join(terms))

        if len(entries) > self.max_bullets:
            bullets.append(f"• …и ещё {len(entries) - self.max_bullets} публикаций")

        return "\n".join(bullets)
