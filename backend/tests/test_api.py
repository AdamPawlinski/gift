from contextlib import asynccontextmanager
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from psycopg import errors

from app import email
from app.auth import get_current_profile
from app.config import get_settings
from app.db import get_conn
from app.main import app
from app.schemas import Me


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows

    async def fetchone(self):
        return self.rows[0] if self.rows else None

    async def fetchall(self):
        return self.rows

    async def executemany(self, *_):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        pass


class FakeConn:
    """Replays scripted results in the order the endpoint runs its queries.

    An Exception in the script is raised instead of returned.
    """

    def __init__(self, script):
        self.script = list(script)

    async def execute(self, *_):
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return FakeCursor(item)

    def cursor(self):
        return FakeCursor([])

    @asynccontextmanager
    async def transaction(self):
        yield


class FakeSettings:
    min_participants = 3
    email_cooldown_minutes = 10


def make_me(is_master=False):
    return Me(id=uuid4(), username="Ala", email="ala@example.com", is_master=is_master)


@pytest.fixture
def client():
    app.dependency_overrides[get_settings] = lambda: FakeSettings()
    yield TestClient(app)
    app.dependency_overrides.clear()


def as_user(me, script):
    conn = FakeConn(script)
    app.dependency_overrides[get_current_profile] = lambda: me
    app.dependency_overrides[get_conn] = lambda: conn
    return conn


def test_master_endpoints_forbidden_for_regular_user(client):
    as_user(make_me(), [])
    assert client.post("/api/lottery").status_code == 403
    assert client.delete("/api/lottery/current").status_code == 403
    assert client.get("/api/participants").status_code == 403


def test_start_needs_enough_participants(client):
    as_user(make_me(True), [[{"id": uuid4()}, {"id": uuid4()}]])
    response = client.post("/api/lottery")
    assert response.status_code == 400
    assert response.json()["detail"] == "not_enough_participants"


def test_start_conflicts_when_lottery_active(client):
    ids = [{"id": uuid4()} for _ in range(3)]
    as_user(make_me(True), [ids, errors.UniqueViolation()])
    response = client.post("/api/lottery")
    assert response.status_code == 409
    assert response.json()["detail"] == "lottery_active"


def test_start_creates_lottery(client):
    lottery_id = uuid4()
    ids = [{"id": uuid4()} for _ in range(3)]
    as_user(make_me(True), [ids, [{"id": lottery_id}], []])
    response = client.post("/api/lottery")
    assert response.status_code == 201
    assert response.json() == {"lottery_id": str(lottery_id)}


def test_current_not_started(client):
    as_user(make_me(), [[]])
    assert client.get("/api/lottery/current").json()["status"] == "not_started"


def test_current_finished_with_result(client):
    lottery_id = uuid4()
    as_user(make_me(), [[{"id": lottery_id}], [{"username": "Bartek"}]])
    body = client.get("/api/lottery/current").json()
    assert body == {
        "status": "finished",
        "lottery_id": str(lottery_id),
        "participated": True,
        "receiver_username": "Bartek",
    }


def test_current_finished_for_late_registered_user(client):
    as_user(make_me(), [[{"id": uuid4()}], []])
    body = client.get("/api/lottery/current").json()
    assert body["status"] == "finished"
    assert body["participated"] is False
    assert body["receiver_username"] is None


def test_cancel_without_active_lottery(client):
    as_user(make_me(True), [[]])
    response = client.delete("/api/lottery/current")
    assert response.status_code == 404
    assert response.json()["detail"] == "no_active_lottery"


def test_cancel_returns_no_content(client):
    as_user(make_me(True), [[{"id": uuid4()}], []])
    assert client.delete("/api/lottery/current").status_code == 204


def test_email_rate_limited(client):
    as_user(make_me(), [[{"id": uuid4()}], [{"username": "Bartek"}], [{"e": True}]])
    response = client.post("/api/lottery/current/email")
    assert response.status_code == 429
    assert response.json()["detail"] == "rate_limited"


def test_email_without_result(client):
    as_user(make_me(), [[]])
    assert client.post("/api/lottery/current/email").status_code == 404


def test_email_sent(client, monkeypatch):
    sent = []

    async def fake_send(to, username, receiver):
        sent.append((to, username, receiver))

    monkeypatch.setattr(email, "send_result", fake_send)
    as_user(make_me(), [[{"id": uuid4()}], [{"username": "Bartek"}], [{"e": False}], []])
    assert client.post("/api/lottery/current/email").status_code == 202
    assert sent == [("ala@example.com", "Ala", "Bartek")]
