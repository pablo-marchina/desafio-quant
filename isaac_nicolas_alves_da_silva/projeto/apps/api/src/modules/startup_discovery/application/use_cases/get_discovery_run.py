"""Caso de uso para consultar um DiscoveryRun por id."""

from typing import Callable
from uuid import UUID

from apps.api.src.modules.startup_discovery.application.dto import DiscoveryRunView
from apps.api.src.modules.startup_discovery.application.use_cases.run_discovery import (
    _submission_to_view,
    _to_view,
)
from apps.api.src.modules.startup_discovery.domain.exceptions import (
    DiscoveryRunNotFoundError,
)


class GetDiscoveryRun:

    def __init__(self, uow_factory: Callable) -> None:
        self._uow_factory = uow_factory

    async def execute(self, run_id: UUID) -> DiscoveryRunView:
        async with self._uow_factory() as uow:
            run = await uow.repository.get_by_id(run_id)
            submissions = await uow.repository.list_submissions_for_run(run_id)
        if run is None:
            raise DiscoveryRunNotFoundError(f"DiscoveryRun {run_id} nao encontrado.")
        submitted_urls = [_submission_to_view(submission) for submission in submissions]
        return _to_view(run, submitted_urls)
