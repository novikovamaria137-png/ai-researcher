"""Persistent 'already seen' store — the diff that turns a feed into news."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from pathlib import Path

from .summarizers.base import Entry

log = logging.getLogger(__name__)

#: Ids kept per source. Enough history to survive a slow feed, small enough
#: that the file stays diffable when committed by CI.
MAX_IDS_PER_SOURCE = 400


class SeenStore:
    """Tracks which entry ids each source has already reported.

    Backed by a plain JSON file so a GitHub Actions run can commit it back to
    the repository and keep state between runs without any database.
    """

    def __init__(self, path: str | Path = "data/seen.json") -> None:
        self.path = Path(path)
        self._seen: dict[str, list[str]] = {}
        self._index: dict[str, set[str]] = {}
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            self._seen, self._index = {}, {}
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            log.warning("could not read %s (%s); starting fresh", self.path, exc)
            raw = {}
        self._seen = {k: list(v) for k, v in raw.items() if isinstance(v, list)}
        self._index = {k: set(v) for k, v in self._seen.items()}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {k: v[-MAX_IDS_PER_SOURCE:] for k, v in sorted(self._seen.items())}
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def is_new(self, source: str, uid: str) -> bool:
        return uid not in self._index.get(source, set())

    def filter_new(self, source: str, entries: Iterable[Entry]) -> list[Entry]:
        """Return only entries not seen before, de-duplicated within the batch."""
        fresh: list[Entry] = []
        batch: set[str] = set()
        for entry in entries:
            if entry.uid in batch or not self.is_new(source, entry.uid):
                continue
            batch.add(entry.uid)
            fresh.append(entry)
        return fresh

    def mark(self, source: str, entries: Iterable[Entry]) -> None:
        bucket = self._seen.setdefault(source, [])
        index = self._index.setdefault(source, set())
        for entry in entries:
            if entry.uid not in index:
                bucket.append(entry.uid)
                index.add(entry.uid)

    def is_empty(self) -> bool:
        """True on the very first run — used to avoid a 500-item first digest."""
        return not any(self._seen.values())

    def __len__(self) -> int:
        return sum(len(v) for v in self._seen.values())
