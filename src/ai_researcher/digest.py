"""Assembling competitor sections into one digest message."""

from __future__ import annotations

from datetime import datetime, timezone

from .summarizers.base import CompetitorDigest

TELEGRAM_LIMIT = 4096


def plural(count: int, one: str, few: str, many: str) -> str:
    """Russian plural agreement: 1 публикация / 2 публикации / 5 публикаций."""
    if count % 10 == 1 and count % 100 != 11:
        return one
    if 2 <= count % 10 <= 4 and not 12 <= count % 100 <= 14:
        return few
    return many


def render(
    sections: list[CompetitorDigest],
    title: str = "Конкуренты — что нового",
    backend: str = "extractive",
    now: datetime | None = None,
) -> str:
    """Render the digest as Telegram-friendly Markdown."""
    now = now or datetime.now(timezone.utc)
    stamp = now.strftime("%d.%m.%Y")

    if not sections:
        return f"🔍 *{title}* — {stamp}\n\nНичего нового с прошлого запуска."

    total = sum(len(section.entries) for section in sections)
    parts = [
        f"🔍 *{title}* — {stamp}",
        f"_{total} {plural(total, 'новая публикация', 'новые публикации', 'новых публикаций')}"
        f" у {len(sections)} {plural(len(sections), 'конкурента', 'конкурентов', 'конкурентов')}"
        f" · движок: {backend}_",
        "",
    ]
    for section in sections:
        parts.append(f"*{section.competitor}* ({len(section.entries)})")
        parts.append(section.body.strip())
        parts.append("")
    return "\n".join(parts).strip()


def split_for_telegram(text: str, limit: int = TELEGRAM_LIMIT) -> list[str]:
    """Split a long digest on paragraph boundaries so nothing is truncated."""
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    current = ""
    for block in text.split("\n\n"):
        candidate = f"{current}\n\n{block}" if current else block
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            chunks.append(current)
        while len(block) > limit:
            cut = block.rfind("\n", 0, limit)
            cut = cut if cut > 0 else limit
            chunks.append(block[:cut])
            block = block[cut:].lstrip("\n")
        current = block
    if current:
        chunks.append(current)
    return chunks
