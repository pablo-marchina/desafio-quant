import json
import time

from app.persistence.batch_repository import BatchRepository
from app.persistence.persistence_service import PipelinePersistence
from app.services.batch_processing_service import BatchProcessingService, CuratedStartupLoader
from app.services.batch_worker_service import BatchWorkerService
from tests.test_persistence_service import FakeSupabase


class TrackingRepository(BatchRepository):
    def __init__(self, persistence):
        super().__init__(persistence)
        self.heartbeat_calls = 0

    def heartbeat(self, batch_id, worker_id, lease_seconds=120):
        self.heartbeat_calls += 1
        return super().heartbeat(batch_id, worker_id, lease_seconds)


def test_worker_claims_and_completes_queued_batch(tmp_path):
    curated = tmp_path / "curated.json"
    curated.write_text(
        json.dumps(
            {
                "startups": [
                    {
                        "startup_id": "cubo_alpha",
                        "nome": "Alpha",
                        "site": "https://alpha.example",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    repository = BatchRepository(PipelinePersistence(client=FakeSupabase()))
    service = BatchProcessingService(
        repository,
        loader=CuratedStartupLoader(tmp_path),
        pipeline_runner=lambda payload: {"status": "completo", "errors": []},
    )
    batch_id = service.create_batch("curated.json")
    worker = BatchWorkerService(service, "worker-test")

    assert worker.run_once() is True
    assert repository.get_batch(batch_id)["status"] == "completed"
    assert worker.run_once() is False


def test_worker_renews_lease_during_long_pipeline(tmp_path):
    curated = tmp_path / "curated.json"
    curated.write_text(
        json.dumps({"startups": [{"startup_id": "slow", "nome": "Slow"}]}),
        encoding="utf-8",
    )
    repository = TrackingRepository(PipelinePersistence(client=FakeSupabase()))

    def slow_runner(payload):
        time.sleep(0.06)
        return {"status": "completo", "errors": []}

    service = BatchProcessingService(
        repository,
        loader=CuratedStartupLoader(tmp_path),
        pipeline_runner=slow_runner,
    )
    service.create_batch("curated.json")
    worker = BatchWorkerService(
        service,
        "worker-heartbeat",
        heartbeat_seconds=0.01,
        lease_seconds=1,
    )

    worker.run_once()

    assert repository.heartbeat_calls >= 2
