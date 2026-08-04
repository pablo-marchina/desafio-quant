"""Scraping package.

All public symbols are available via their submodule directly:
  from src.scraping.fetcher import fetch_page
  from src.scraping.http_collector import HttpSourceCollector
  from src.scraping.parser import extract_clean_text
  from src.scraping.cache import scrape_cache
  from src.scraping.strategies import register, resolve
  from src.scraping.youtube_collector import fetch_transcript, extract_video_id
  from src.scraping.rss_collector import collect_feed
  from src.scraping.pdf_collector import extract_pdf
  from src.scraping.fuzzy_dedup import FuzzyIndex, exact_dedup
  etc.
"""
