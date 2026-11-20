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


def make_me(is_master=False, in_draw=True):
    return Me(
        id=uuid4(),
        username="Ala",
        email="ala@example.com",
        draw_id=uuid4() if in_draw else None,
        draw_name="Rodzina" if in_draw else None,
        is_master=is_master,
    )


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
    as_user(make_me(True), [[], [{"id": uuid4()}, {"id": uuid4()}]])
    response = client.post("/api/lottery")
    assert response.status_code == 400
    assert response.json()["detail"] == "not_enough_participants"


def test_start_conflicts_when_lottery_active(client):
    ids = [{"id": uuid4()} for _ in range(3)]
    as_user(make_me(True), [[], ids, errors.UniqueViolation()])
    response = client.post("/api/lottery")
    assert response.status_code == 409
    assert response.json()["detail"] == "lottery_active"


def test_start_creates_lottery(client):
    lottery_id = uuid4()
    ids = [{"id": uuid4()} for _ in range(3)]
    as_user(make_me(True), [[], ids, [{"id": lottery_id}], []])
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


class FakeAdmin:
    def __init__(self, error=None):
        self.deleted = []
        self.error = error
        self.auth = type("A", (), {"admin": self})()

    def delete_user(self, user_id):
        if self.error:
            raise self.error
        self.deleted.append(user_id)


def delete_setup(monkeypatch, valid=True, admin=None):
    from app.routers import me as me_router

    async def fake_verify(email, password):
        return valid

    admin = admin or FakeAdmin()
    monkeypatch.setattr(me_router, "verify_password", fake_verify)
    monkeypatch.setattr(me_router, "get_admin_client", lambda: admin)
    return admin


def test_delete_account_wrong_password(client, monkeypatch):
    admin = delete_setup(monkeypatch, valid=False)
    conn = as_user(make_me(), [])
    response = client.post("/api/me/delete", json={"password": "bad"})
    assert response.status_code == 403
    assert response.json()["detail"] == "wrong_password"
    assert admin.deleted == [] and conn.script == []


def test_delete_account_without_draw(client, monkeypatch):
    admin = delete_setup(monkeypatch)
    me = make_me(in_draw=False)
    conn = as_user(me, [[], []])
    response = client.post("/api/me/delete", json={"password": "pw"})
    assert response.status_code == 204
    assert admin.deleted == [str(me.id)]
    assert conn.script == []


def test_delete_account_member_cancels_lottery(client, monkeypatch):
    admin = delete_setup(monkeypatch)
    me = make_me()
    conn = as_user(me, [[{"id": uuid4()}], [], [], [], [], []])
    response = client.post("/api/me/delete", json={"password": "pw"})
    assert response.status_code == 204
    assert admin.deleted == [str(me.id)]
    assert conn.script == []


def test_delete_account_master_closes_draw(client, monkeypatch):
    admin = delete_setup(monkeypatch)
    me = make_me(is_master=True)
    conn = as_user(me, [[{"id": uuid4()}], [], [], [], [], [], []])
    response = client.post("/api/me/delete", json={"password": "pw"})
    assert response.status_code == 204
    assert admin.deleted == [str(me.id)]
    assert conn.script == []


def test_delete_account_auth_failure(client, monkeypatch):
    from supabase_auth.errors import AuthApiError

    delete_setup(monkeypatch, admin=FakeAdmin(AuthApiError("boom", 500, "unexpected_failure")))
    as_user(make_me(in_draw=False), [[], []])
    response = client.post("/api/me/delete", json={"password": "pw"})
    assert response.status_code == 502
    assert response.json()["detail"] == "delete_failed"


def test_delete_account_requires_password(client):
    as_user(make_me(), [])
    assert client.post("/api/me/delete", json={}).status_code == 422


@pytest.mark.parametrize(
    ("status_code", "expected"), [(200, True), (400, False)]
)
async def test_verify_password(monkeypatch, status_code, expected):
    import httpx

    from app import supabase_admin

    transport = httpx.MockTransport(lambda request: httpx.Response(status_code))
    real = httpx.AsyncClient
    monkeypatch.setattr(
        supabase_admin.httpx, "AsyncClient", lambda **kw: real(transport=transport, **kw)
    )
    assert await supabase_admin.verify_password("a@example.com", "pw") is expected


async def test_verify_password_upstream_error(monkeypatch):
    import httpx
    from fastapi import HTTPException

    from app import supabase_admin

    transport = httpx.MockTransport(lambda request: httpx.Response(500))
    real = httpx.AsyncClient
    monkeypatch.setattr(
        supabase_admin.httpx, "AsyncClient", lambda **kw: real(transport=transport, **kw)
    )
    with pytest.raises(HTTPException) as exc:
        await supabase_admin.verify_password("a@example.com", "pw")
    assert exc.value.status_code == 502


def test_current_without_draw(client):
    as_user(make_me(in_draw=False), [])
    assert client.get("/api/lottery/current").json()["status"] == "no_draw"


def test_master_endpoints_forbidden_without_draw(client):
    as_user(make_me(in_draw=False), [])
    assert client.post("/api/lottery").status_code == 403
    assert client.get("/api/participants").status_code == 403


def test_email_without_draw(client):
    as_user(make_me(in_draw=False), [])
    assert client.post("/api/lottery/current/email").status_code == 404


def test_list_draws(client):
    draw = {"id": uuid4(), "name": "Rodzina", "members": 2}
    as_user(make_me(in_draw=False), [[draw]])
    body = client.get("/api/draws").json()
    assert body == [{**draw, "id": str(draw["id"])}]


def test_create_draw(client):
    draw_id = uuid4()
    as_user(make_me(in_draw=False), [[{"id": draw_id, "name": "Rodzina"}], [{"id": uuid4()}], []])
    response = client.post("/api/draws", json={"name": "  Rodzina "})
    assert response.status_code == 201
    assert response.json() == {"id": str(draw_id), "name": "Rodzina", "members": 1}


def test_create_draw_when_already_in_draw(client):
    as_user(make_me(), [])
    response = client.post("/api/draws", json={"name": "Praca"})
    assert response.status_code == 409
    assert response.json()["detail"] == "already_in_draw"


def test_create_draw_name_taken(client):
    as_user(make_me(in_draw=False), [errors.UniqueViolation()])
    response = client.post("/api/draws", json={"name": "Rodzina"})
    assert response.status_code == 409
    assert response.json()["detail"] == "draw_name_taken"


def test_create_draw_name_limits(client):
    as_user(make_me(in_draw=False), [])
    assert client.post("/api/draws", json={"name": "a" * 51}).status_code == 422
    assert client.post("/api/draws", json={"name": "   "}).status_code == 422
    assert client.post("/api/draws", json={}).status_code == 422


def test_join_draw(client):
    as_user(make_me(in_draw=False), [[{"id": uuid4()}], [], [{"id": uuid4()}], []])
    assert client.post(f"/api/draws/{uuid4()}/join").status_code == 204


def test_join_when_already_in_draw(client):
    as_user(make_me(), [])
    response = client.post(f"/api/draws/{uuid4()}/join")
    assert response.status_code == 409
    assert response.json()["detail"] == "already_in_draw"


def test_join_closed_draw(client):
    as_user(make_me(in_draw=False), [[]])
    response = client.post(f"/api/draws/{uuid4()}/join")
    assert response.status_code == 404
    assert response.json()["detail"] == "draw_not_found"


def test_join_draw_with_results(client):
    as_user(make_me(in_draw=False), [[{"id": uuid4()}], [{"id": uuid4()}]])
    response = client.post(f"/api/draws/{uuid4()}/join")
    assert response.status_code == 409
    assert response.json()["detail"] == "lottery_active"


def test_join_race_already_in_draw(client):
    as_user(make_me(in_draw=False), [[{"id": uuid4()}], [], []])
    response = client.post(f"/api/draws/{uuid4()}/join")
    assert response.status_code == 409
    assert response.json()["detail"] == "already_in_draw"


def test_leave_without_draw(client):
    as_user(make_me(in_draw=False), [])
    response = client.post("/api/me/draw/leave")
    assert response.status_code == 404
    assert response.json()["detail"] == "not_in_draw"


def test_member_leaves_without_results(client):
    conn = as_user(make_me(), [[], [], []])
    assert client.post("/api/me/draw/leave").status_code == 204
    assert conn.script == []


def test_member_leaves_and_cancels_results(client):
    conn = as_user(make_me(), [[{"id": uuid4()}], [], [], []])
    assert client.post("/api/me/draw/leave").status_code == 204
    assert conn.script == []


def test_master_leaves_and_closes_draw(client):
    conn = as_user(make_me(is_master=True), [[{"id": uuid4()}], [], [], [], []])
    assert client.post("/api/me/draw/leave").status_code == 204
    assert conn.script == []
