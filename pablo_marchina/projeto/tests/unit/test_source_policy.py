from src.extraction.schemas import SourceType
from src.scraping.source_policy import classify_source, source_quality_score


def test_classify_news_source() -> None:
    assert classify_source("https://neofeed.com.br/startups/exemplo") == SourceType.NEWS


def test_source_quality_score_official_site() -> None:
    assert source_quality_score(SourceType.OFFICIAL_SITE) == 1.0


def test_source_quality_score_news() -> None:
    assert source_quality_score(SourceType.NEWS) == 0.8


def test_source_quality_score_unknown_type() -> None:
    assert source_quality_score(SourceType.JOB_POST) == 0.5


def test_source_quality_score_all_types_have_scores() -> None:
    for st in SourceType:
        score = source_quality_score(st)
        assert 0.0 <= score <= 1.0, f"{st} has score {score} out of range"
