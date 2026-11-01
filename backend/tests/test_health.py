from fastapi.testclient import TestClient

from app.main import app


def test_health_without_lifespan():
    # No `with`: the lifespan (DB pool) is not started.
    assert TestClient(app).get("/api/health").json() == {"status": "ok"}
