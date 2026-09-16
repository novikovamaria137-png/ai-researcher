"""End-to-end CLI behaviour, with the network stubbed out."""

import httpx
import pytest

from ai_researcher import cli, sources


@pytest.fixture
def offline_feed(monkeypatch, rss_bytes):
    def fake_get(url, **kwargs):
        return httpx.Response(200, content=rss_bytes, request=httpx.Request("GET", url))

    monkeypatch.setattr(sources.httpx, "get", fake_get)


def test_dry_run_prints_digest_and_leaves_state_untouched(
    offline_feed, tmp_path, capsys, monkeypatch
):
    monkeypatch.delenv("TG_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TG_CHAT_ID", raising=False)
    state = tmp_path / "seen.json"

    code = cli.main(
        ["--preset", "ai", "--backend", "extractive", "--dry-run", "--state", str(state)]
    )

    assert code == 0
    out = capsys.readouterr().out
    assert "Competitor A launches" in out
    assert "OpenAI" in out  # section header from the preset
    assert not state.exists()  # dry-run writes nothing


def test_second_run_reports_nothing_new(offline_feed, tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("TG_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TG_CHAT_ID", raising=False)
    state = tmp_path / "seen.json"
    args = ["--preset", "ai", "--backend", "extractive", "--state", str(state)]

    assert cli.main(args) == 0
    capsys.readouterr()
    assert state.exists()

    assert cli.main(args) == 0
    assert "Ничего нового" in capsys.readouterr().out


def test_first_run_is_capped(offline_feed, tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("TG_BOT_TOKEN", raising=False)
    cli.main(["--preset", "ai", "--backend", "extractive", "--dry-run",
              "--state", str(tmp_path / "seen.json")])
    out = capsys.readouterr().out
    # 4 sources x 3 capped entries; without the cap the feed would flood the digest.
    assert "12 новых публикаций" in out


def test_unknown_backend_exits_with_code_2(offline_feed, tmp_path, capsys):
    code = cli.main(["--backend", "nope", "--dry-run", "--state", str(tmp_path / "s.json")])
    assert code == 2
    assert "Ошибка бэкенда" in capsys.readouterr().err


def test_unknown_preset_exits_with_code_2(capsys):
    assert cli.main(["--preset", "nope", "--dry-run"]) == 2
    assert "Ошибка конфигурации" in capsys.readouterr().err
