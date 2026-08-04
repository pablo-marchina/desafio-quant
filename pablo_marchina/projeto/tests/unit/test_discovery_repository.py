from __future__ import annotations

from pathlib import Path

import pytest

from src.database.session import configure_product_database, reset_product_database_runtime
from src.repositories.discovery import DiscoveryRepository


@pytest.fixture
def repository(tmp_path: Path) -> DiscoveryRepository:
    runtime = configure_product_database(f"sqlite:///{(tmp_path / 'disc.db').as_posix()}")
    session = runtime.session_factory()
    yield DiscoveryRepository(session)
    session.close()
    reset_product_database_runtime()


class TestDiscoveryRuns:
    def test_create_and_list_runs(self, repository: DiscoveryRepository) -> None:
        run = repository.create_discovery_run(
            source_id="manual_seed_br_ai_startups",
            query_json={"type": "manual_seed"},
        )
        repository.session.commit()
        assert run.id is not None
        assert run.status == "queued"
        assert run.source_id == "manual_seed_br_ai_startups"

        runs = repository.list_discovery_runs()
        assert len(runs) == 1
        assert runs[0].id == run.id

    def test_complete_run(self, repository: DiscoveryRepository) -> None:
        run = repository.create_discovery_run(source_id="test")
        repository.session.commit()
        completed = repository.complete_discovery_run(
            run.id,
            results_count=10,
            candidates_created=5,
            duplicates_found=2,
        )
        repository.session.commit()
        assert completed.status == "completed"
        assert completed.results_count == 10
        assert completed.candidates_created == 5
        assert completed.completed_at is not None

    def test_fail_run(self, repository: DiscoveryRepository) -> None:
        run = repository.create_discovery_run()
        repository.session.commit()
        failed = repository.fail_discovery_run(run.id, error_message="Network error")
        repository.session.commit()
        assert failed.status == "failed"
        assert failed.error_message == "Network error"

    def test_degrade_run(self, repository: DiscoveryRepository) -> None:
        run = repository.create_discovery_run(source_id="test")
        repository.session.commit()
        degraded = repository.degrade_discovery_run(
            run.id,
            error_message="Partial fetch failure",
            results_count=5,
            candidates_created=3,
        )
        repository.session.commit()
        assert degraded.status == "degraded"
        assert degraded.error_message == "Partial fetch failure"

    def test_list_runs_filtered_by_status(self, repository: DiscoveryRepository) -> None:
        r1 = repository.create_discovery_run(source_id="src1")
        repository.create_discovery_run(source_id="src2")
        repository.session.commit()
        repository.complete_discovery_run(r1.id)
        repository.session.commit()

        completed = repository.list_discovery_runs(status="completed")
        queued = repository.list_discovery_runs(status="queued")

        assert len(completed) == 1
        assert len(queued) == 1

    def test_get_run_not_found(self, repository: DiscoveryRepository) -> None:
        assert repository.get_discovery_run("nonexistent") is None


class TestCandidates:
    def test_create_and_list_candidates(self, repository: DiscoveryRepository) -> None:
        c = repository.create_candidate(
            source_id="test",
            discovered_name="Test AI",
            normalized_name="test ai",
            website="https://test.ai",
            sector="AI",
            confidence="medium",
        )
        repository.session.commit()
        assert c.id is not None
        assert c.status == "new"

        candidates = repository.list_candidates()
        assert len(candidates) == 1

    def test_create_candidates_bulk(self, repository: DiscoveryRepository) -> None:
        items = [
            {
                "source_id": "test",
                "discovered_name": "AI One",
                "normalized_name": "ai one",
                "website": "https://one.ai",
                "sector": "AI",
            },
            {
                "source_id": "test",
                "discovered_name": "AI Two",
                "normalized_name": "ai two",
                "website": "https://two.ai",
                "sector": "AI",
            },
        ]
        created = repository.create_candidates_bulk(items)
        repository.session.commit()
        assert len(created) == 2

    def test_list_candidates_filters(self, repository: DiscoveryRepository) -> None:
        repository.create_candidate(
            source_id="src_a",
            discovered_name="High AI",
            normalized_name="high ai",
            website="https://high.ai",
            sector="AI",
            confidence="high",
            ai_native_signals_json={"signal_count": 5},
        )
        repository.create_candidate(
            source_id="src_b",
            discovered_name="Low AI",
            normalized_name="low ai",
            website="https://low.ai",
            sector="AI",
            confidence="low",
        )
        repository.session.commit()

        by_source = repository.list_candidates(source_id="src_a")
        assert len(by_source) == 1

        by_confidence = repository.list_candidates(confidence_min=0.7)
        assert len(by_confidence) == 1

        by_signal = repository.list_candidates(ai_native_signal=True)
        assert len(by_signal) == 1

    def test_mark_duplicate(self, repository: DiscoveryRepository) -> None:
        c = repository.create_candidate(
            source_id="test",
            discovered_name="Dup AI",
            normalized_name="dup ai",
        )
        repository.session.commit()
        result = repository.mark_duplicate(c.id, duplicate_of_candidate_id="other")
        repository.session.commit()
        assert result is not None
        assert result.status == "duplicate"
        assert result.metadata_json["duplicate_of_candidate_id"] == "other"

    def test_promote_candidate(self, repository: DiscoveryRepository) -> None:
        c = repository.create_candidate(
            source_id="test",
            discovered_name="Promo AI",
            normalized_name="promo ai",
            website="https://promo.ai",
        )
        repository.session.commit()
        result = repository.promote_candidate(c.id, startup_id="startup_123")
        repository.session.commit()
        assert result is not None
        assert result.status == "promoted"
        assert result.promoted_startup_id == "startup_123"

    def test_find_duplicate_candidate(self, repository: DiscoveryRepository) -> None:
        repository.create_candidate(
            source_id="test",
            discovered_name="Radar AI",
            normalized_name="radar ai",
            website="https://radar.ai",
        )
        repository.session.commit()
        found = repository.find_duplicate_candidate(
            normalized_name="radar ai",
            website="https://other.ai",
        )
        assert found is not None
        assert found.normalized_name == "radar ai"

        not_found = repository.find_duplicate_candidate(
            normalized_name="unknown",
            website="https://unknown.ai",
        )
        assert not_found is None

    def test_update_candidate_status(self, repository: DiscoveryRepository) -> None:
        c = repository.create_candidate(
            source_id="test",
            discovered_name="Update AI",
            normalized_name="update ai",
        )
        repository.session.commit()
        updated = repository.update_candidate_status(c.id, status="reviewed")
        repository.session.commit()
        assert updated is not None
        assert updated.status == "reviewed"

    def test_update_candidate_fields(self, repository: DiscoveryRepository) -> None:
        c = repository.create_candidate(
            source_id="test",
            discovered_name="Field AI",
            normalized_name="field ai",
            sector="Old Sector",
        )
        repository.session.commit()
        updated = repository.update_candidate_fields(c.id, {"sector": "New Sector", "confidence": "high"})
        repository.session.commit()
        assert updated is not None
        assert updated.sector == "New Sector"
        assert updated.confidence == "high"
