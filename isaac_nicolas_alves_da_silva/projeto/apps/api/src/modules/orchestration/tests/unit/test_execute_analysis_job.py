"""Testes do caso de uso ExecuteAnalysisJob."""

from types import TracebackType
from uuid import UUID, uuid4

import pytest

from apps.api.src.modules.orchestration.application.dto import (
    CreateAnalysisJobInput,
)
from apps.api.src.modules.orchestration.application.ports import (
    BriefingPort,
    RecommendationsPort,
)
from apps.api.src.modules.orchestration.application.unit_of_work import (
    AnalysisUnitOfWork,
)
from apps.api.src.modules.orchestration.application.use_cases.execute_analysis_job import (
    ExecuteAnalysisJob,
)
from apps.api.src.modules.orchestration.domain.entities import AnalysisJob
from apps.api.src.modules.orchestration.domain.enums import AnalysisJobStatus
from apps.api.src.modules.orchestration.domain.exceptions import (
    StartupProfileUnavailableError,
)
from apps.api.src.modules.orchestration.domain.repositories import (
    AnalysisJobRepository,
)


class FakeRecommendationsPort(RecommendationsPort):
    def __init__(self, *, count: int = 0, error: Exception | None = None) -> None:
        self._count = count
        self._error = error

    async def generate(self, startup_id: UUID) -> int:
        if self._error is not None:
            raise self._error
        return self._count


class FakeBriefingPort(BriefingPort):
    def __init__(self, *, briefing_id: UUID | None = None) -> None:
        self._briefing_id = briefing_id or uuid4()

    async def generate(self, startup_id: UUID) -> UUID:
        return self._briefing_id


class FakeAnalysisJobRepository(AnalysisJobRepository):
    def __init__(self) -> None:
        self.items: dict[UUID, AnalysisJob] = {}
        self.save_count = 0

    async def save(self, analysis_job: AnalysisJob) -> None:
        self.save_count += 1
        self.items[analysis_job.id] = analysis_job

    async def get_by_id(self, analysis_job_id: UUID) -> AnalysisJob | None:
        return self.items.get(analysis_job_id)

    async def list_by_startup_id(self, startup_id: UUID) -> list[AnalysisJob]:
        return [job for job in self.items.values() if job.startup_id == startup_id]


class FakeUoW(AnalysisUnitOfWork):
    def __init__(self, repository: FakeAnalysisJobRepository) -> None:
        self.analysis_job_repository = repository

    async def __aenter__(self) -> "FakeUoW":
        return self

    async def __aexit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        pass

    async def commit(self) -> None:
        pass

    async def rollback(self) -> None:
        pass


@pytest.mark.anyio
async def test_execute_completes_job_with_aggregated_result() -> None:
    startup_id = uuid4()
    briefing_id = uuid4()
    repository = FakeAnalysisJobRepository()
    uow = FakeUoW(repository)
    use_case = ExecuteAnalysisJob(
        lambda: uow,
        FakeRecommendationsPort(count=3),
        FakeBriefingPort(briefing_id=briefing_id),
    )

    view = await use_case.execute(CreateAnalysisJobInput(startup_id=startup_id))

    assert view.status is AnalysisJobStatus.COMPLETED
    assert view.recommendation_count == 3
    assert view.briefing_id == briefing_id
    assert repository.save_count == 2


@pytest.mark.anyio
async def test_execute_marks_job_failed_when_profile_unavailable() -> None:
    startup_id = uuid4()
    repository = FakeAnalysisJobRepository()
    uow = FakeUoW(repository)
    use_case = ExecuteAnalysisJob(
        lambda: uow,
        FakeRecommendationsPort(error=StartupProfileUnavailableError("nao encontrada")),
        FakeBriefingPort(),
    )

    with pytest.raises(StartupProfileUnavailableError):
        await use_case.execute(CreateAnalysisJobInput(startup_id=startup_id))

    saved_jobs = list(repository.items.values())
    assert len(saved_jobs) == 1
    assert saved_jobs[0].status is AnalysisJobStatus.FAILED
    assert saved_jobs[0].error_message == "nao encontrada"
