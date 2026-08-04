"""Models SQLAlchemy das tabelas pertencentes ao módulo de scraping."""

from .scraping_attempt_model import ScrapingAttemptModel
from .scraping_job_model import ScrapingJobModel
from .scraping_result_model import ScrapingResultModel

__all__ = [
    "ScrapingAttemptModel",
    "ScrapingJobModel",
    "ScrapingResultModel",
]
