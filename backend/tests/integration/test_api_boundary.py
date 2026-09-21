from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_health_and_unconfigured_readiness():
    with TestClient(create_app(Settings(environment="test", database_url=None))) as client:
        assert client.get("/health").json()["status"] == "ok"
        response = client.get("/ready")
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "DATABASE_UNAVAILABLE"


def test_business_routes_require_authentication():
    with TestClient(create_app(Settings(environment="test", database_url=None))) as client:
        for path in (
            "/api/v1/cases",
            "/api/v1/emails",
            "/api/v1/jobs/00000000-0000-4000-8000-000000000001",
        ):
            response = client.get(path)
            assert response.status_code == 401
            assert response.json()["error"]["code"] == "AUTH_REQUIRED"
            assert response.json()["error"]["request_id"]


def test_cors_rejects_unapproved_origin():
    with TestClient(create_app(Settings(environment="test", database_url=None))) as client:
        response = client.options(
            "/api/v1/cases",
            headers={"Origin": "https://untrusted.example", "Access-Control-Request-Method": "GET"},
        )
        assert response.status_code == 400
        assert "access-control-allow-origin" not in response.headers


def test_openapi_contains_typed_separate_routes():
    schema = create_app(Settings(environment="test", database_url=None)).openapi()
    assert "/api/v1/verify" in schema["paths"]
    assert "/api/v1/cases/{case_id}/previews" in schema["paths"]
    assert schema["components"]["schemas"]["VerifyRequest"]["additionalProperties"] is False
