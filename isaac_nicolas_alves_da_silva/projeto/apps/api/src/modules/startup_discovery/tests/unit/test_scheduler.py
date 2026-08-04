import asyncio
from dataclasses import dataclass
from uuid import uuid4

import pytest

from apps.api.src.modules.startup_discovery.application.scheduler import (
    StartupDiscoveryScheduler,
)
from apps.api.src.modules.startup_discovery.domain.enums import DiscoveryRunStatus


@dataclass(frozen=True)
class FakeDiscoveryRunView:
    id: object
    status: DiscoveryRunStatus
    jobs_submitted: int


class FakeRunDiscovery:
    def __init__(self, calls: list[str], executed: asyncio.Event) -> None:
        self._calls = calls
        self._executed = executed

    async def execute(self) -> FakeDiscoveryRunView:
        self._calls.append("execute")
        self._executed.set()
        return FakeDiscoveryRunView(
            id=uuid4(),
            status=DiscoveryRunStatus.COMPLETED,
            jobs_submitted=3,
        )


@pytest.mark.anyio
async def test_scheduler_runs_once_on_startup() -> None:
    calls: list[str] = []
    executed = asyncio.Event()
    scheduler = StartupDiscoveryScheduler(
        run_discovery_factory=lambda: FakeRunDiscovery(calls, executed),
        interval_seconds=3600,
        run_on_startup=True,
    )

    scheduler.start()
    await asyncio.wait_for(executed.wait(), timeout=1)
    await scheduler.stop()

    assert calls == ["execute"]
    assert not scheduler.is_running


@pytest.mark.anyio
async def test_scheduler_rejects_invalid_interval() -> None:
    with pytest.raises(ValueError):
        StartupDiscoveryScheduler(
            run_discovery_factory=lambda: FakeRunDiscovery([], asyncio.Event()),
            interval_seconds=0,
        )
