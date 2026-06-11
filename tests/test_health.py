"""Smoke tests for public unauthenticated endpoints."""
from app.main import create_app


def test_health_endpoint_is_public(temp_db):
    app, _ = create_app()
    client = app.test_client()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}
