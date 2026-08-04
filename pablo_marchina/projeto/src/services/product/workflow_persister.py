"""Adapter: ProductRepository → PersistWorkflowResultService protocol.

Usage::

    from src.services.product.workflow_persister import make_workflow_persister

    persister = make_workflow_persister(session)
    persister("ar-123", status="brief_generated", output_snapshot={...})
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from src.repositories.product import ProductRepository


def make_workflow_persister(session: Session) -> Any:
    """Return a callable matching the ``PersistWorkflowResultService`` protocol.

    The returned callable wraps ``ProductRepository.update_analysis_run_status``
    and commits the session after a successful update.
    """

    repo = ProductRepository(session)

    def _persist(
        analysis_run_id: str,
        *,
        status: str,
        output_snapshot: dict[str, Any],
        error_message: str | None = None,
    ) -> None:
        repo.update_analysis_run_status(
            analysis_run_id,
            status=status,
            completed_at=datetime.now(UTC),
            error_message=error_message,
            output_snapshot=output_snapshot,
        )
        session.commit()

    return _persist
