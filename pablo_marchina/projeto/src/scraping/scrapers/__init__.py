import src.scraping.scrapers.ace_scraper  # noqa: F401
import src.scraping.scrapers.bossa_scraper  # noqa: F401
import src.scraping.scrapers.cubo_scraper  # noqa: F401
import src.scraping.scrapers.distrito_scraper  # noqa: F401
import src.scraping.scrapers.inovativa_scraper  # noqa: F401
import src.scraping.scrapers.openstartups_scraper  # noqa: F401
from src.scraping.scrapers.base_scraper import SourceScraper, scraper_registry

__all__ = ["SourceScraper", "scraper_registry"]
