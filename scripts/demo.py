#!/usr/bin/env python3
"""Офлайн-демо: собирает дайджест из встроенного фида.

Ни сети, ни ключей, ни аккаунтов — запускается сразу после `git clone`.
Нужно, чтобы любой, кто открыл репозиторий, за 10 секунд увидел результат.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import feedparser  # noqa: E402

from ai_researcher import digest  # noqa: E402
from ai_researcher.sources import clean_text  # noqa: E402
from ai_researcher.summarizers import ExtractiveSummarizer  # noqa: E402
from ai_researcher.summarizers.base import CompetitorDigest, Entry  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "sample_feed.xml"


def main() -> int:
    parsed = feedparser.parse(FIXTURE.read_bytes())
    entries = [
        Entry(
            uid=item.get("id", item.link),
            title=clean_text(item.title, limit=300),
            link=item.link,
            summary=clean_text(item.get("summary", "")),
            published=item.get("published", ""),
            source="Competitor A",
        )
        for item in parsed.entries
    ]

    engine = ExtractiveSummarizer()
    section = CompetitorDigest(
        competitor="Competitor A",
        body=engine.summarize("Competitor A", entries),
        entries=entries,
    )

    print(digest.render([section], title="DEMO — что нового у конкурентов",
                        backend=engine.name))
    print("\n[демо на встроенных данных: сеть и ключи не использовались]", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
