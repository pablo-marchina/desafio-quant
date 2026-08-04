import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from app.persistence.batch_repository import BatchRepository
from app.persistence.persistence_service import PipelinePersistence
from app.services.batch_processing_service import BatchProcessingService, CuratedStartupLoader
from app.services.batch_worker_service import BatchWorkerService
from tests.test_persistence_service import FakeSupabase


def _curated_file(path, count=100):
    startups = [
        {"startup_id": f"synthetic-{index:03d}", "nome": f"Synthetic {index:03d}"}
        for index in range(count)
    ]
    file = path / "load.json"
    file.write_text(json.dumps({"startups": startups}), encoding="utf-8")
    return startups


def test_two_workers_process_100_cached_items_without_duplicates(tmp_path):
    startups = _curated_file(tmp_path)
    repository = BatchRepository(PipelinePersistence(client=FakeSupabase()))
    processed = []
    lock = threading.Lock()

    def cached_runner(payload):
        with lock:
            processed.append(payload["external_id"])
        return {"status": "completo", "errors": []}

    service = BatchProcessingService(
        repository,
        loader=CuratedStartupLoader(tmp_path),
        pipeline_runner=cached_runner,
    )
    first_ids = [item["startup_id"] for item in startups[:50]]
    second_ids = [item["startup_id"] for item in startups[50:]]
    batch_ids = [
        service.create_batch("load.json", {"startup_ids": first_ids}),
        service.create_batch("load.json", {"startup_ids": second_ids}),
    ]
    workers = [
        BatchWorkerService(service, "load-worker-a", heartbeat_seconds=0.01),
        BatchWorkerService(service, "load-worker-b", heartbeat_seconds=0.01),
    ]

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda worker: worker.run_once(), workers))
    duration = time.perf_counter() - started

    assert results == [True, True]
    assert duration < 30 * 60
    assert len(processed) == 100
    assert len(set(processed)) == 100
    assert all(repository.get_batch(batch_id)["status"] == "completed" for batch_id in batch_ids)


def test_expired_worker_lease_recovers_interrupted_item_once(tmp_path):
    _curated_file(tmp_path, count=1)
    repository = BatchRepository(PipelinePersistence(client=FakeSupabase()))
    executions = []
    service = BatchProcessingService(
        repository,
        loader=CuratedStartupLoader(tmp_path),
        pipeline_runner=lambda payload: executions.append(payload["external_id"])
        or {"status": "completo", "errors": []},
    )
    batch_id = service.create_batch("load.json")
    repository.claim_next_batch("dead-worker", lease_seconds=0)
    item = repository.list_items(batch_id)[0]
    repository.start_item(__import__("uuid").UUID(item["id"]))

    assert repository.recover_stale_batches(stale_after_minutes=0) == 1
    recovered = repository.list_items(batch_id)[0]
    assert recovered["status"] == "pending"

    worker = BatchWorkerService(service, "replacement-worker")
    assert worker.run_once() is True
    assert executions == ["synthetic-000"]
    assert repository.get_batch(batch_id)["status"] == "completed"
