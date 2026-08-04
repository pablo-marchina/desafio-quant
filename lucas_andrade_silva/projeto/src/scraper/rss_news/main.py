from __future__ import annotations

import argparse
import json
from pathlib import Path

import feedparser

from . import config
from .extractor import entry_to_rows, is_recent


def collect(feeds: tuple[str, ...], *, lookback_days: int, max_entries_per_feed: int) -> list[dict]:
    rows: list[dict] = []
    for feed_url in feeds:
        parsed = feedparser.parse(feed_url)
        if getattr(parsed, "bozo", False):
            error = getattr(parsed, "bozo_exception", None)
            raise RuntimeError(f"Falha ao ler feed RSS {feed_url}: {error}")
        for entry in list(parsed.entries or [])[:max_entries_per_feed]:
            if not is_recent(entry, lookback_days=lookback_days):
                continue
            rows.extend(
                entry_to_rows(
                    entry,
                    feed_url=feed_url,
                    source_name=config.SOURCE_NAME,
                    keywords=config.KEYWORDS,
                )
            )
    return rows


def run(
    *,
    feeds: tuple[str, ...] | None = None,
    output: Path | None = None,
    dry_run: bool = False,
    lookback_days: int | None = None,
    max_entries_per_feed: int | None = None,
) -> int:
    selected_feeds = feeds or config.FEEDS
    if not selected_feeds:
        raise RuntimeError("Defina RSS_NEWS_FEEDS com uma lista de feeds RSS separados por virgula ou nova linha")
    rows = collect(
        selected_feeds,
        lookback_days=lookback_days if lookback_days is not None else config.LOOKBACK_DAYS,
        max_entries_per_feed=max_entries_per_feed if max_entries_per_feed is not None else config.MAX_ENTRIES_PER_FEED,
    )
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    if not dry_run:
        from scraper.startupbase_api.database import connect, ensure_schema, upsert_startups

        with connect() as connection:
            ensure_schema(connection)
            upsert_startups(rows, connection)
    print(f"Concluido: {len(rows)} candidatos de noticias RSS" + (" (sem gravar no banco)" if dry_run else " enviados ao Supabase"))
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Coleta candidatos de startups a partir de RSS de noticias")
    parser.add_argument("--feed", action="append", help="URL de feed RSS; pode ser repetido")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--lookback-days", type=int)
    parser.add_argument("--max-entries-per-feed", type=int)
    args = parser.parse_args()
    run(
        feeds=tuple(args.feed or ()) or None,
        output=args.output,
        dry_run=args.dry_run,
        lookback_days=args.lookback_days,
        max_entries_per_feed=args.max_entries_per_feed,
    )


if __name__ == "__main__":
    main()
