from radar.graph.progress import PipelineTracker


def test_tracker_complete_preserves_existing_detail_when_no_detail_is_passed(monkeypatch):
    calls = []

    def fake_update_run_step_status(*args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setattr(
        "radar.graph.progress.update_run_step_status",
        fake_update_run_step_status,
    )

    tracker = PipelineTracker(run_id=42)
    tracker.set_detail("extractor", "101 claims extraidas: 30 IA")
    tracker.complete("extractor")

    assert calls[-1][1] == {"status": "completed", "detail": None}