from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.routes.auth import AuthenticatedPrincipal, decode_supabase_token, get_current_principal
from app.routes.dependencies import get_batch_service, get_persistence
from tests.test_api import AUTH, FakeBatchService, FakePersistence


def _signed_token(monkeypatch, expires_in=60, role="analyst"):
    issuer = "https://project.supabase.co/auth/v1"
    monkeypatch.setenv("SUPABASE_JWT_ISSUER", issuer)
    monkeypatch.setenv("SUPABASE_JWT_AUDIENCE", "authenticated")
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": "user-123",
            "aud": "authenticated",
            "iss": issuer,
            "exp": now + timedelta(seconds=expires_in),
            "iat": now,
            "jti": "session-token-123",
            "app_metadata": {"radar_role": role},
        },
        private_key,
        algorithm="RS256",
    )
    return token, private_key.public_key()


def test_supabase_jwt_validates_signature_expiration_and_role(monkeypatch):
    token, public_key = _signed_token(monkeypatch, role="analyst")

    principal = decode_supabase_token(token, signing_key=public_key)

    assert principal.subject == "user-123"
    assert principal.role == "analyst"
    assert principal.token_id == "session-token-123"


def test_expired_jwt_is_rejected(monkeypatch):
    token, public_key = _signed_token(monkeypatch, expires_in=-1)

    with pytest.raises(HTTPException) as error:
        decode_supabase_token(token, signing_key=public_key)

    assert error.value.status_code == 401
    assert error.value.detail == "Token expirado"


def test_readonly_role_cannot_create_batch(monkeypatch):
    monkeypatch.setenv("BACKEND_API_KEY", "test-api-key")
    service = FakeBatchService()
    app.dependency_overrides[get_current_principal] = lambda: AuthenticatedPrincipal(
        subject="reader", role="readonly", auth_method="jwt"
    )
    app.dependency_overrides[get_persistence] = lambda: FakePersistence()
    app.dependency_overrides[get_batch_service] = lambda: service
    try:
        with TestClient(app) as client:
            response = client.post("/api/v1/batches", json={"limit": 1})
        assert response.status_code == 403
        assert service.runs == []
    finally:
        app.dependency_overrides.clear()


def test_legacy_api_key_is_disabled_in_production(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("ALLOW_LEGACY_API_KEY", raising=False)
    monkeypatch.setenv("BACKEND_API_KEY", "test-api-key")
    app.dependency_overrides[get_persistence] = lambda: FakePersistence()
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/startups", headers=AUTH)
        assert response.status_code == 401
    finally:
        app.dependency_overrides.clear()


class RateLimitedDatabase:
    def table(self, name):
        from tests.test_api import FakeQuery

        return FakeQuery([])

    def rpc(self, name, payload):
        return SimpleNamespace(
            execute=lambda: SimpleNamespace(
                data={"allowed": False, "remaining": 0, "retry_after": 42}
            )
        )


def test_rate_limit_returns_429_with_retry_after():
    persistence = type("Persistence", (), {"db": RateLimitedDatabase()})()
    app.dependency_overrides[get_current_principal] = lambda: AuthenticatedPrincipal(
        subject="reader", role="readonly", auth_method="jwt"
    )
    app.dependency_overrides[get_persistence] = lambda: persistence
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/startups")
        assert response.status_code == 429
        assert response.headers["Retry-After"] == "42"
    finally:
        app.dependency_overrides.clear()


class RevokedDatabase:
    def table(self, name):
        from tests.test_api import FakeQuery

        if name == "revoked_auth_tokens":
            return FakeQuery([{"token_id": "revoked-token"}])
        return FakeQuery([])


def test_revoked_token_is_rejected_before_route_execution():
    persistence = type("Persistence", (), {"db": RevokedDatabase()})()
    app.dependency_overrides[get_current_principal] = lambda: AuthenticatedPrincipal(
        subject="reader",
        role="readonly",
        auth_method="jwt",
        token_id="revoked-token",
    )
    app.dependency_overrides[get_persistence] = lambda: persistence
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/startups")
        assert response.status_code == 401
        assert response.json()["detail"] == "Token revogado"
    finally:
        app.dependency_overrides.clear()
