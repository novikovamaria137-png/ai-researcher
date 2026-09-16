"""Where a finished digest goes: Telegram, stdout, or a Markdown file."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import httpx

from .digest import split_for_telegram

log = logging.getLogger(__name__)


class DeliveryError(RuntimeError):
    """Raised when a channel is configured but refuses the message."""


def send_telegram(text: str, token: str | None = None, chat_id: str | None = None) -> int:
    """Send the digest to a Telegram chat. Returns the number of messages sent.

    A bot token is free: talk to @BotFather, then get your chat id from
    @userinfobot. No paid tier is involved anywhere in this path.
    """
    token = token or os.environ.get("TG_BOT_TOKEN", "")
    chat_id = chat_id or os.environ.get("TG_CHAT_ID", "")
    if not token or not chat_id:
        raise DeliveryError("TG_BOT_TOKEN / TG_CHAT_ID are not set")

    sent = 0
    for chunk in split_for_telegram(text):
        response = httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": chunk,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True,
            },
            timeout=30.0,
        )
        if response.status_code >= 400:
            # Markdown in feed titles (*, _, [) can break Telegram's parser —
            # retry the same chunk as plain text rather than losing the digest.
            log.warning("telegram rejected Markdown (%s); retrying as plain text",
                        response.status_code)
            response = httpx.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": chunk, "disable_web_page_preview": True},
                timeout=30.0,
            )
        if response.status_code >= 400:
            raise DeliveryError(f"telegram HTTP {response.status_code}: {response.text[:200]}")
        sent += 1
    return sent


def write_markdown(text: str, directory: str | Path = "digests") -> Path:
    """Archive the digest as a dated Markdown file (nice for the repo/portfolio)."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{datetime.now(timezone.utc):%Y-%m-%d}.md"
    path.write_text(text + "\n", encoding="utf-8")
    return path


def print_console(text: str) -> None:
    print(text)


def telegram_configured() -> bool:
    return bool(os.environ.get("TG_BOT_TOKEN") and os.environ.get("TG_CHAT_ID"))
