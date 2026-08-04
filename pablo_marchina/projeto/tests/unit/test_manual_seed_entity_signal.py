from __future__ import annotations

from src.database.session import configure_product_database, product_session, reset_product_database_runtime
from src.discovery.service import StartupDiscoveryService


def test_sector_label_is_not_counted_as_entity_ai_evidence(tmp_path) -> None:
    reset_product_database_runtime()
    configure_product_database(f"sqlite:///{(tmp_path / 'seed.db').as_posix()}")
    with product_session() as session:
        result = StartupDiscoveryService(session).run_manual_seed_discovery(
            [
                {
                    "name": "Generic Workflow Co",
                    "website": "https://generic-workflow.example.org",
                    "sector": "Health AI",
                    "description": "Coordinates appointments and patient journeys.",
                    "raw_text_excerpt": "Coordinates appointments and patient journeys.",
                    "source_url": "https://generic-workflow.example.org",
                    "source_type": "official_site",
                }
            ],
            source_id="entity_signal_test",
        )

    assert result["candidates_created"] == 0
    assert result["rejected_invalid_entities"] == 1
    assert result["duplicates_found"] == 0
