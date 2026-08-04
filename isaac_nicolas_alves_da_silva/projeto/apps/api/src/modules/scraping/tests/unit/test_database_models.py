"""Testes estruturais dos models SQLAlchemy do módulo de scraping."""

from apps.api.src.database.relational.base import Base
from apps.api.src.modules.scraping.infrastructure.database.models import (
    ScrapingAttemptModel,
    ScrapingJobModel,
    ScrapingResultModel,
)


def test_all_scraping_tables_are_registered_in_shared_metadata() -> None:
    """Alembic precisa encontrar as três tabelas no metadata compartilhado."""

    assert {
        ScrapingJobModel.__tablename__,
        ScrapingAttemptModel.__tablename__,
        ScrapingResultModel.__tablename__,
    } <= set(Base.metadata.tables)


def test_result_owns_the_single_job_result_relationship() -> None:
    """A relação 1:1 deve existir sem uma FK circular no job."""

    job_foreign_keys = ScrapingJobModel.__table__.foreign_keys
    result_job_id = ScrapingResultModel.__table__.c.job_id

    assert not job_foreign_keys
    assert result_job_id.unique is True
    assert {
        foreign_key.target_fullname
        for foreign_key in ScrapingResultModel.__table__.foreign_keys
    } == {"scraping_jobs.id"}


def test_score_constraints_are_present() -> None:
    """PostgreSQL deve impedir scores fora do intervalo de zero a um."""

    attempt_constraint_names = {
        constraint.name for constraint in ScrapingAttemptModel.__table__.constraints
    }
    result_constraint_names = {
        constraint.name for constraint in ScrapingResultModel.__table__.constraints
    }

    expected_attempt_constraints = {
        "ck_scraping_attempts_technical_score_range",
        "ck_scraping_attempts_text_score_range",
        "ck_scraping_attempts_evidence_score_range",
        "ck_scraping_attempts_quality_score_range",
    }
    expected_result_constraints = {
        "ck_scraping_results_technical_score_range",
        "ck_scraping_results_text_score_range",
        "ck_scraping_results_evidence_score_range",
        "ck_scraping_results_quality_score_range",
    }

    assert expected_attempt_constraints <= attempt_constraint_names
    assert expected_result_constraints <= result_constraint_names
