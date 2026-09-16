import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ai_researcher.summarizers.base import Entry  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def entries() -> list[Entry]:
    return [
        Entry(
            uid="a1",
            title="Competitor A launches an AI assistant for enterprise support",
            link="https://example.com/a1",
            summary=(
                "Competitor A announced a new AI assistant aimed at enterprise support "
                "teams. The product routes tickets automatically and drafts replies. "
                "Pricing starts at $49 per seat and the beta opens next month. "
                "The company says early customers cut handling time by a third."
            ),
            published="Mon, 14 Sep 2026 09:00:00 GMT",
            source="Competitor A",
        ),
        Entry(
            uid="a2",
            title="Competitor A announces a partnership with a payments provider",
            link="https://example.com/a2",
            summary=(
                "The partnership adds embedded checkout to the platform. "
                "It covers twelve European markets at launch. "
                "Rollout to North America is planned for the first quarter."
            ),
            published="Sun, 13 Sep 2026 12:00:00 GMT",
            source="Competitor A",
        ),
    ]


@pytest.fixture
def rss_bytes() -> bytes:
    return (FIXTURES / "sample_feed.xml").read_bytes()
