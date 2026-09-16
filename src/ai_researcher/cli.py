"""Command-line entry point: fetch → diff → summarize → deliver."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import delivery, digest, sources, summarizers
from .config import Config, available_presets
from .state import SeenStore
from .summarizers.base import CompetitorDigest

log = logging.getLogger("ai_researcher")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ai-researcher",
        description="Ежедневный дайджест новостей конкурентов в Telegram. "
                    "Работает без платных API-ключей.",
    )
    parser.add_argument(
        "--preset", default="ai",
        help=f"набор источников: {', '.join(available_presets()) or 'ai, fashion'}",
    )
    parser.add_argument("--config", help="путь к своему YAML вместо пресета")
    parser.add_argument(
        "--backend", default=None,
        help="движок суммаризации: auto | " + " | ".join(sorted(summarizers.REGISTRY)),
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="напечатать дайджест в консоль и не трогать Telegram и состояние",
    )
    parser.add_argument("--save-markdown", action="store_true",
                        help="дополнительно сохранить дайджест в digests/")
    parser.add_argument("--state", help="путь к seen.json")
    parser.add_argument("--limit", type=int, default=None,
                        help="сколько записей брать из каждого фида")
    parser.add_argument("--full-first-run", action="store_true",
                        help="не ограничивать размер самого первого дайджеста")
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser


def collect(config: Config, store: SeenStore, first_run: bool, cap_first_run: bool
            ) -> list[CompetitorDigest]:
    """Fetch every source and keep only entries not reported before."""
    collected: list[CompetitorDigest] = []
    for source in config.sources:
        entries = sources.fetch(source, limit=config.max_entries_per_source)
        fresh = store.filter_new(source.name, entries)
        if first_run and cap_first_run:
            # A first run would otherwise dump a whole feed's backlog.
            fresh = fresh[:3]
        if not fresh:
            log.info("%s: нет нового", source.name)
            continue
        fresh = fresh[: config.max_new_per_source]
        log.info("%s: %d новых", source.name, len(fresh))
        collected.append(CompetitorDigest(competitor=source.name, body="", entries=fresh))
    return collected


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    try:
        config = Config.load(preset=args.preset, path=args.config)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Ошибка конфигурации: {exc}", file=sys.stderr)
        return 2

    if args.backend:
        config.backend = args.backend
    if args.limit:
        config.max_entries_per_source = args.limit
    state_path = Path(args.state) if args.state else config.state_path

    store = SeenStore(state_path)
    first_run = store.is_empty()

    try:
        primary = summarizers.build(config.backend)
    except summarizers.SummarizerError as exc:
        print(f"Ошибка бэкенда: {exc}", file=sys.stderr)
        return 2
    engine = summarizers.FallbackSummarizer(primary)
    log.info("движок суммаризации: %s", primary.name)

    sections = collect(config, store, first_run, cap_first_run=not args.full_first_run)
    for section in sections:
        section.body = engine.summarize(section.competitor, section.entries)

    text = digest.render(sections, title=config.title, backend=primary.name)

    if args.dry_run:
        delivery.print_console(text)
        print(f"\n--- dry-run: Telegram не вызывался, {state_path} не обновлялся ---",
              file=sys.stderr)
        return 0

    if args.save_markdown:
        path = delivery.write_markdown(text)
        print(f"Сохранено: {path}", file=sys.stderr)

    if delivery.telegram_configured():
        try:
            sent = delivery.send_telegram(text)
            print(f"Отправлено в Telegram: {sent} сообщени(й)", file=sys.stderr)
        except delivery.DeliveryError as exc:
            print(f"Telegram недоступен ({exc}); печатаю в консоль", file=sys.stderr)
            delivery.print_console(text)
    else:
        print("TG_BOT_TOKEN/TG_CHAT_ID не заданы — печатаю дайджест в консоль",
              file=sys.stderr)
        delivery.print_console(text)

    for section in sections:
        store.mark(section.competitor, section.entries)
    store.save()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
