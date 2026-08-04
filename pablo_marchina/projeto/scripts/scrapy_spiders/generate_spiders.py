#!/usr/bin/env python3
"""Generate Scrapy spiders for large-scale directory crawling.

Usage:
    python scripts/scrapy_spiders/generate_spiders.py --source all
    python scripts/scrapy_spiders/generate_spiders.py --source distrito

Output:
    scripts/scrapy_spiders/spiders/<source_id>.py

Then run with::

    cd scripts/scrapy_spiders
    scrapy crawl distrito -o distrito.json
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

SPIDERS_DIR = Path(__file__).resolve().parent / "spiders"

DIRECTORY_CONFIGS: dict[str, dict[str, str]] = {
    "distrito": {
        "base_url": "https://www.distrito.me/startups",
        "page_param": "page",
        "start_page": "1",
        "allowed_domains": "distrito.me",
        "item_css": ".startup-card",
        "name_css": "h3::text",
        "link_css": "a::attr(href)",
    },
    "cubo": {
        "base_url": "https://cubo.network/members",
        "page_param": "pagina",
        "start_page": "1",
        "allowed_domains": "cubo.network",
        "item_css": ".member-card",
        "name_css": ".name::text",
        "link_css": "a[href]::attr(href)",
    },
    "openstartups": {
        "base_url": "https://openstartups.net",
        "page_param": "pagina",
        "start_page": "1",
        "allowed_domains": "openstartups.net",
        "item_css": "tr",
        "name_css": "td.name::text",
        "link_css": "a::attr(href)",
    },
    "startse": {
        "base_url": "https://startse.com/startups",
        "page_param": "page",
        "start_page": "1",
        "allowed_domains": "startse.com",
        "item_css": ".startup-item",
        "name_css": "h2::text",
        "link_css": "a::attr(href)",
    },
}

SPIDER_TEMPLATE = '''import scrapy


class {class_name}Spider(scrapy.Spider):
    name = "{source_id}"
    allowed_domains = ["{allowed_domains}"]
    start_urls = ["{base_url}"]

    page_param = "{page_param}"
    start_page = "{start_page}"

    def parse(self, response):
        for item in response.css("{item_css}"):
            yield {{
                "url": item.css("{link_css}").get(),
                "title": item.css("{name_css}").get(),
                "source_id": "{source_id}",
            }}

        # Pagination
        current = int(response.url.split(self.page_param + "=")[-1]) if self.page_param + "=" in response.url else int(self.start_page)
        next_page = current + 1
        sep = "&" if "?" in response.url else "?"
        yield scrapy.Request(
            url=f"{{response.url.split(sep)[0]}}{sep}{self.page_param}={next_page}",
            callback=self.parse,
        )
'''


def generate_spider(source_id: str, config: dict[str, str]) -> str:
    """Generate a Scrapy spider file for the given directory source."""
    class_name = source_id.title().replace("_", "")
    spider_code = SPIDER_TEMPLATE.format(
        class_name=class_name,
        source_id=source_id,
        **config,
    )

    output_dir = SPIDERS_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / f"{source_id}_spider.py"
    output_path.write_text(spider_code, encoding="utf-8")
    logger.info("Generated spider: %s", output_path)
    return str(output_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Scrapy spiders for directory crawling")
    parser.add_argument("--source", type=str, default="all", help="Source ID or 'all'")
    args = parser.parse_args()

    if args.source == "all":
        sources = list(DIRECTORY_CONFIGS.keys())
    elif args.source in DIRECTORY_CONFIGS:
        sources = [args.source]
    else:
        logger.error("Unknown source '%s'. Available: %s", args.source, ", ".join(DIRECTORY_CONFIGS.keys()))
        sys.exit(1)

    generated = []
    for sid in sources:
        path = generate_spider(sid, DIRECTORY_CONFIGS[sid])
        generated.append(path)

    if generated:
        logger.info("")
        logger.info("To run a spider:")
        logger.info("    cd %s", SPIDERS_DIR)
        logger.info("    scrapy crawl <source_id> -o output.json")
        logger.info("")
        logger.info("Then ingest into pipeline:")
        logger.info("    python -c \"from src.scraping.scrapy_bridge import ScrapyBridge;")
        logger.info("    bridge = ScrapyBridge(); results = bridge.ingest('output.json')\"")
    else:
        logger.warning("No spiders generated.")


if __name__ == "__main__":
    main()
