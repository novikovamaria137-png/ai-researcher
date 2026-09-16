"""Fetching competitor publications from RSS/Atom feeds and plain changelogs."""

from __future__ import annotations

import hashlib
import html
import logging
import re
from dataclasses import dataclass
from typing import Any

import feedparser
import httpx

from .summarizers.base import Entry

log = logging.getLogger(__name__)

USER_AGENT = "ai-researcher/1.0 (+https://github.com/novikovamaria137-png)"
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


@dataclass
class Source:
    """One competitor to watch."""

    name: str
    rss: str | None = None
    changelog: str | None = None
    note: str = ""

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Source:
        if "name" not in raw:
            raise ValueError(f"source is missing 'name': {raw!r}")
        if not raw.get("rss") and not raw.get("changelog"):
            raise ValueError(f"source {raw['name']!r} needs either 'rss' or 'changelog'")
        return cls(
            name=str(raw["name"]),
            rss=raw.get("rss"),
            changelog=raw.get("changelog"),
            note=str(raw.get("note", "")),
        )


def clean_text(raw: str, limit: int = 1200) -> str:
    """Strip tags/entities from feed summaries and collapse whitespace."""
    text = html.unescape(_TAG.sub(" ", raw or ""))
    text = _WS.sub(" ", text).strip()
    return text[:limit]


def _uid(source_name: str, candidate: str) -> str:
    digest = hashlib.sha1(f"{source_name}|{candidate}".encode()).hexdigest()
    return digest[:16]


def fetch_rss(source: Source, limit: int = 20, timeout: float = 20.0) -> list[Entry]:
    """Parse a feed into :class:`Entry` objects. Network errors yield []."""
    assert source.rss
    try:
        response = httpx.get(
            source.rss,
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        )
        response.raise_for_status()
        parsed = feedparser.parse(response.content)
    except httpx.HTTPError as exc:
        log.warning("%s: feed unreachable (%s)", source.name, exc)
        return []

    entries: list[Entry] = []
    for item in parsed.entries[:limit]:
        link = getattr(item, "link", "") or ""
        title = clean_text(getattr(item, "title", ""), limit=300) or "(без заголовка)"
        raw_summary = getattr(item, "summary", "") or getattr(item, "description", "")
        entries.append(
            Entry(
                uid=_uid(source.name, getattr(item, "id", "") or link or title),
                title=title,
                link=link,
                summary=clean_text(raw_summary),
                published=clean_text(getattr(item, "published", ""), limit=60),
                source=source.name,
            )
        )
    return entries


def fetch_changelog(source: Source, limit: int = 20, timeout: float = 20.0) -> list[Entry]:
    """Very small HTML fallback for competitors without a feed.

    Pulls headings off the page and treats each as an item. Intentionally
    simple — a real scraper belongs behind Playwright (see README, Roadmap).
    """
    assert source.changelog
    try:
        response = httpx.get(
            source.changelog,
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        log.warning("%s: changelog unreachable (%s)", source.name, exc)
        return []

    try:
        from bs4 import BeautifulSoup
    except ImportError:  # pragma: no cover - optional dependency
        log.warning("beautifulsoup4 is not installed; skipping %s", source.name)
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    entries: list[Entry] = []
    for heading in soup.find_all(["h2", "h3"])[:limit]:
        title = clean_text(heading.get_text(" "), limit=300)
        if not title:
            continue
        sibling = heading.find_next(["p", "li"])
        body = clean_text(sibling.get_text(" ")) if sibling else ""
        entries.append(
            Entry(
                uid=_uid(source.name, title),
                title=title,
                link=source.changelog,
                summary=body,
                source=source.name,
            )
        )
    return entries


def fetch(source: Source, limit: int = 20) -> list[Entry]:
    """Fetch a source by whichever channel it declares."""
    if source.rss:
        return fetch_rss(source, limit=limit)
    return fetch_changelog(source, limit=limit)
