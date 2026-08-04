from scraper.rss_news.extractor import entry_to_rows, extract_company_names


def test_extract_company_names_from_news_title():
    assert extract_company_names("Fintech Acme recebe aporte para expandir IA no Brasil") == ["Acme"]


def test_entry_to_rows_builds_raw_candidate():
    entry = {
        "title": "Startup Nuvem AI capta rodada seed",
        "summary": "A startup brasileira usa inteligencia artificial para automacao.",
        "link": "https://news.example/nuvem-ai",
    }
    rows = entry_to_rows(
        entry,
        feed_url="https://news.example/rss",
        source_name="RSS News",
        keywords=("startup", "inteligencia artificial"),
    )
    assert len(rows) == 1
    assert rows[0]["company_name"] == "Nuvem AI"
    assert rows[0]["source_name"] == "RSS News: news.example"
    assert rows[0]["source_url"] == "https://news.example/nuvem-ai"
