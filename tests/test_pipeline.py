"""State diffing, feed parsing, digest rendering and config loading."""

import httpx
import pytest

from ai_researcher import digest, sources
from ai_researcher.config import Config, available_presets
from ai_researcher.digest import split_for_telegram
from ai_researcher.sources import Source, clean_text
from ai_researcher.state import SeenStore
from ai_researcher.summarizers.base import CompetitorDigest

# --- state ---------------------------------------------------------------

def test_seen_store_filters_already_reported(tmp_path, entries):
    store = SeenStore(tmp_path / "seen.json")
    assert store.is_empty()
    assert len(store.filter_new("Competitor A", entries)) == 2

    store.mark("Competitor A", entries)
    store.save()
    assert store.filter_new("Competitor A", entries) == []

    reloaded = SeenStore(tmp_path / "seen.json")
    assert not reloaded.is_empty()
    assert reloaded.filter_new("Competitor A", entries) == []


def test_seen_store_deduplicates_within_one_batch(tmp_path, entries):
    store = SeenStore(tmp_path / "seen.json")
    assert len(store.filter_new("Competitor A", entries + entries)) == 2


def test_seen_store_survives_a_corrupt_file(tmp_path):
    path = tmp_path / "seen.json"
    path.write_text("{ this is not json", encoding="utf-8")
    store = SeenStore(path)
    assert store.is_empty()


def test_sources_are_tracked_independently(tmp_path, entries):
    store = SeenStore(tmp_path / "seen.json")
    store.mark("Competitor A", entries)
    assert len(store.filter_new("Competitor B", entries)) == 2


# --- sources -------------------------------------------------------------

def test_fetch_rss_parses_entries(monkeypatch, rss_bytes):
    def fake_get(url, **kwargs):
        return httpx.Response(200, content=rss_bytes, request=httpx.Request("GET", url))

    monkeypatch.setattr(sources.httpx, "get", fake_get)
    result = sources.fetch(Source(name="Competitor A", rss="https://example.com/feed.xml"))

    assert len(result) == 3
    assert result[0].title.startswith("Competitor A launches")
    assert result[0].link == "https://example.com/a1"
    assert "<p>" not in result[0].summary  # HTML stripped
    assert len({e.uid for e in result}) == 3  # stable, unique ids


def test_fetch_rss_returns_empty_on_network_error(monkeypatch):
    def boom(url, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(sources.httpx, "get", boom)
    assert sources.fetch(Source(name="X", rss="https://example.com/feed")) == []


def test_source_requires_a_channel():
    with pytest.raises(ValueError):
        Source.from_dict({"name": "X"})


def test_clean_text_unescapes_and_truncates():
    assert clean_text("<b>a&amp;b</b>") == "a&b"
    assert len(clean_text("x" * 5000, limit=100)) == 100


# --- digest --------------------------------------------------------------

def test_render_reports_counts_and_backend(entries):
    text = digest.render(
        [CompetitorDigest(competitor="Competitor A", body="• bullet", entries=entries)],
        backend="extractive",
    )
    assert "Competitor A" in text
    assert "2 новые публикации" in text
    assert "extractive" in text


def test_render_handles_no_news():
    assert "Ничего нового" in digest.render([])


def test_split_for_telegram_respects_the_limit():
    text = "\n\n".join(["блок " + "x" * 300 for _ in range(60)])
    chunks = split_for_telegram(text)
    assert len(chunks) > 1
    assert all(len(chunk) <= 4096 for chunk in chunks)
    assert sum(len(c) for c in chunks) >= len(text) - 2 * len(chunks)


def test_split_for_telegram_leaves_short_text_alone():
    assert split_for_telegram("короткий дайджест") == ["короткий дайджест"]


# --- config --------------------------------------------------------------

@pytest.mark.parametrize("preset", ["ai", "fashion"])
def test_presets_load_and_declare_sources(preset):
    config = Config.load(preset)
    assert config.sources
    assert all(s.rss or s.changelog for s in config.sources)
    assert config.backend


def test_both_presets_are_discoverable():
    assert {"ai", "fashion"} <= set(available_presets())


def test_env_overrides_backend(monkeypatch):
    monkeypatch.setenv("SUMMARIZER_BACKEND", "extractive")
    assert Config.load("ai").backend == "extractive"


def test_missing_preset_is_reported(tmp_path):
    with pytest.raises(FileNotFoundError):
        Config.load("does-not-exist")


def test_entry_prompt_block_includes_link(entries):
    block = entries[0].as_prompt_block()
    assert "https://example.com/a1" in block
    assert block.startswith("## ")
