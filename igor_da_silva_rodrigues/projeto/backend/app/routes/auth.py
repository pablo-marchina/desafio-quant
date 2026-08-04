from __future__ import annotations

import hmac
import os
from dataclasses import dataclass
from typing import Literal, cast

import jwt
from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient


Role = Literal["admin", "analyst", "readonly"]


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    subject: str
    role: Role
    auth_method: Literal["jwt", "legacy_api_key"]
    token_id: str | None = None


api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)
metrics_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_principal(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    provided_api_key: str | None = Security(api_key_header),
) -> AuthenticatedPrincipal:
    if credentials and credentials.scheme.lower() == "bearer":
        return decode_supabase_token(credentials.credentials)
    if _legacy_api_key_allowed() and _valid_api_key(provided_api_key):
        return AuthenticatedPrincipal(
            subject="legacy-api-key",
            role="admin",
            auth_method="legacy_api_key",
        )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token Bearer valido obrigatorio",
        headers={"WWW-Authenticate": "Bearer"},
    )


def decode_supabase_token(token: str, signing_key: object | None = None) -> AuthenticatedPrincipal:
    jwks_url = os.getenv("SUPABASE_JWKS_URL")
    issuer = os.getenv("SUPABASE_JWT_ISSUER") or _default_issuer()
    audience = os.getenv("SUPABASE_JWT_AUDIENCE", "authenticated")
    if signing_key is None:
        if not jwks_url:
            raise _unauthorized("SUPABASE_JWKS_URL nao configurada")
        try:
            signing_key = PyJWKClient(jwks_url, cache_keys=True).get_signing_key_from_jwt(token).key
        except Exception as exc:
            raise _unauthorized("Nao foi possivel resolver a chave de assinatura") from exc
    try:
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256", "ES256"],
            audience=audience,
            issuer=issuer,
            options={"require": ["exp", "sub", "aud", "iss"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise _unauthorized("Token expirado") from exc
    except jwt.PyJWTError as exc:
        raise _unauthorized("Token invalido") from exc
    role = _extract_role(claims)
    token_id = claims.get("jti") or claims.get("session_id")
    return AuthenticatedPrincipal(
        subject=str(claims["sub"]),
        role=role,
        auth_method="jwt",
        token_id=str(token_id) if token_id else None,
    )


def require_api_key(
    principal: AuthenticatedPrincipal = Security(get_current_principal),
) -> AuthenticatedPrincipal:
    """Compatibility alias for integrations migrating from API key to JWT."""
    return principal


def require_metrics_token(
    credentials: HTTPAuthorizationCredentials | None = Security(metrics_bearer_scheme),
) -> None:
    expected = os.getenv("METRICS_BEARER_TOKEN")
    if not expected:
        raise HTTPException(status_code=503, detail="METRICS_BEARER_TOKEN nao configurado")
    if not credentials or not hmac.compare_digest(credentials.credentials, expected):
        raise HTTPException(
            status_code=401,
            detail="Token de metricas invalido",
            headers={"WWW-Authenticate": "Bearer"},
        )


def _extract_role(claims: dict) -> Role:
    app_metadata = claims.get("app_metadata") or {}
    user_metadata = claims.get("user_metadata") or {}
    role = (
        app_metadata.get("radar_role")
        or user_metadata.get("radar_role")
        or claims.get("radar_role")
        or "readonly"
    )
    return cast(Role, role) if role in {"admin", "analyst", "readonly"} else "readonly"


def _legacy_api_key_allowed() -> bool:
    explicit = os.getenv("ALLOW_LEGACY_API_KEY")
    if explicit is not None:
        return explicit.lower() in {"1", "true", "yes"}
    return os.getenv("ENVIRONMENT", "development").lower() != "production"


def _valid_api_key(provided: str | None) -> bool:
    expected = os.getenv("BACKEND_API_KEY")
    return bool(expected and provided and hmac.compare_digest(provided, expected))


def _default_issuer() -> str:
    base = os.getenv("SUPABASE_URL", "").rstrip("/")
    return f"{base}/auth/v1" if base else ""


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )
