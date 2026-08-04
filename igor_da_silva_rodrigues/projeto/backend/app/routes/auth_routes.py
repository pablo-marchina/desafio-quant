from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.persistence.persistence_service import PipelinePersistence
from app.routes.auth import AuthenticatedPrincipal
from app.routes.dependencies import get_persistence
from app.routes.security import require_roles


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class RevokeTokenRequest(BaseModel):
    token_id: str = Field(min_length=8, max_length=200)
    expires_at: datetime
    reason: str | None = Field(default=None, max_length=500)


@router.post("/revoke", status_code=201)
def revoke_token(
    request: RevokeTokenRequest,
    principal: AuthenticatedPrincipal = Depends(require_roles("admin")),
    persistence: PipelinePersistence = Depends(get_persistence),
) -> dict[str, str]:
    persistence.db.table("revoked_auth_tokens").upsert(
        {
            "token_id": request.token_id,
            "expires_at": request.expires_at.isoformat(),
            "revoked_by": principal.subject,
            "reason": request.reason,
        },
        on_conflict="token_id",
    ).execute()
    return {"status": "revoked", "token_id": request.token_id}
