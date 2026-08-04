from __future__ import annotations

import os
from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, Response, status

from app.persistence.persistence_service import PipelinePersistence
from app.routes.auth import AuthenticatedPrincipal, Role, get_current_principal
from app.routes.dependencies import get_persistence


ROLE_LIMITS = {"readonly": 60, "analyst": 120, "admin": 300}


def enforce_security(
    request: Request,
    response: Response,
    principal: AuthenticatedPrincipal = Depends(get_current_principal),
    persistence: PipelinePersistence = Depends(get_persistence),
) -> AuthenticatedPrincipal:
    if principal.token_id and _is_revoked(persistence, principal.token_id):
        raise HTTPException(status_code=401, detail="Token revogado")
    limit = int(os.getenv(f"RATE_LIMIT_{principal.role.upper()}_PER_MINUTE", ROLE_LIMITS[principal.role]))
    client_host = request.client.host if request.client else "unknown"
    identity = principal.token_id or principal.subject or client_host
    result = _consume_rate_limit(persistence, f"{principal.auth_method}:{identity}", limit)
    response.headers["X-RateLimit-Limit"] = str(limit)
    response.headers["X-RateLimit-Remaining"] = str(result.get("remaining", limit))
    if not result.get("allowed", True):
        retry_after = int(result.get("retry_after", 60))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Limite de requisicoes excedido",
            headers={"Retry-After": str(retry_after)},
        )
    return principal


def require_roles(*roles: Role) -> Callable:
    def dependency(principal: AuthenticatedPrincipal = Depends(enforce_security)):
        if principal.role not in roles:
            raise HTTPException(status_code=403, detail="Permissao insuficiente")
        return principal

    return dependency


def _is_revoked(persistence: PipelinePersistence, token_id: str) -> bool:
    response = (
        persistence.db.table("revoked_auth_tokens")
        .select("token_id")
        .eq("token_id", token_id)
        .limit(1)
        .execute()
    )
    return bool(response.data)


def _consume_rate_limit(
    persistence: PipelinePersistence,
    key: str,
    limit: int,
) -> dict:
    rpc = getattr(persistence.db, "rpc", None)
    if not callable(rpc):
        return {"allowed": True, "remaining": limit}
    response = rpc(
        "consume_api_rate_limit",
        {"p_key": key, "p_limit": limit, "p_window_seconds": 60},
    ).execute()
    data = response.data or {}
    if isinstance(data, list):
        data = data[0] if data else {}
    return dict(data)
