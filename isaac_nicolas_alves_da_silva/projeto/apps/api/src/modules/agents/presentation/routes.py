"""Rotas HTTP do modulo agents."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from apps.api.src.modules.agents.domain.exceptions import (
    AgentRunNotFoundError,
    AgentServiceUnavailableError,
)
from apps.api.src.modules.agents.factories.agents_factory import AgentsFactory

from .schemas import AgentRunResponse, ResumeAgentRunRequest

router = APIRouter(
    prefix="/agents",
    tags=["agents"],
)


@router.get(
    "/runs/{run_id}",
    response_model=AgentRunResponse,
)
async def get_agent_run(run_id: UUID) -> AgentRunResponse:
    """Consulta o estado de uma execucao de agente.

    Quando o status e ``waiting_human_review``, o campo ``interrupt_value``
    contem a pergunta que o grafo fez ao revisor humano.
    """

    use_case = AgentsFactory.create_get_agent_run_use_case()
    try:
        view = await use_case.execute(run_id=run_id)
    except AgentRunNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    return AgentRunResponse.from_view(view)


@router.post(
    "/runs/{run_id}/resume",
    response_model=AgentRunResponse,
    status_code=status.HTTP_200_OK,
)
async def resume_agent_run(
    run_id: UUID,
    body: ResumeAgentRunRequest,
) -> AgentRunResponse:
    """Retoma uma execucao pausada aguardando revisao humana.

    Chame este endpoint quando o status do run for ``waiting_human_review``.
    O campo ``interrupt_value`` do GET informa o que o agente precisa que o
    revisor decida. Envie a decisao em ``resume_value``.

    Para o Evidence Validation Agent: ``'approved'`` aceita a evidencia,
    qualquer outro valor a rejeita.
    """

    use_case = AgentsFactory.create_resume_agent_job()
    try:
        await use_case.execute(run_id=run_id, resume_value=body.resume_value)
    except AgentRunNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except AgentServiceUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error

    get_use_case = AgentsFactory.create_get_agent_run_use_case()
    view = await get_use_case.execute(run_id=run_id)
    return AgentRunResponse.from_view(view)
