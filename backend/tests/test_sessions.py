"""Session API tests; SQLite runs offline, PostgreSQL uses migrated schema."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import get_session
from app.main import app
from app.models import User, UserLanguagePreference
from app.sessions import COOKIE_NAME, read_identity, sign_identity

SECRET = b"test-only-secret-with-at-least-32-bytes"


@pytest.fixture(params=["sqlite", "postgresql"])
def session_db(request):
    if request.param == "postgresql":
        connection = request.getfixturevalue("db")
        with Session(connection, join_transaction_mode="create_savepoint") as db:
            yield db
    else:
        engine = create_engine(
            "sqlite://", poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
        User.__table__.create(engine)
        UserLanguagePreference.__table__.create(engine)
        with Session(engine) as db:
            yield db
        engine.dispose()


@pytest.fixture
def client(session_db, monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", SECRET.decode())
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "true")

    def override_db():
        yield session_db

    app.dependency_overrides[get_session] = override_db
    try:
        with TestClient(app, base_url="https://testserver") as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_session)


def test_new_and_returning_browser(client, session_db):
    response = client.post("/api/v1/session")
    assert response.status_code == 200
    assert response.json() == {
        "initial_test_completed": False,
        "onboarding_completed": False,
        "next_route": "/test",
    }
    cookie = client.cookies.get(COOKIE_NAME)
    user = session_db.get(User, read_identity(cookie, SECRET))
    assert user.taxonomy_version == "2.0"
    assert user.created_at is not None
    assert response.headers["cache-control"] == "no-store"
    for attribute in [
        "HttpOnly", "Secure", "SameSite=lax", "Path=/", "Max-Age=31536000",
    ]:
        assert attribute in response.headers["set-cookie"]
    assert client.post("/api/v1/session").json() == response.json()
    assert client.cookies.get(COOKIE_NAME) == cookie
    assert session_db.scalar(select(func.count()).select_from(User)) == 1
    # A fresh client with the persisted cookie resolves the same database user.
    with TestClient(app, base_url="https://testserver") as returning:
        returning.cookies.set(COOKIE_NAME, cookie, domain="testserver.local")
        assert returning.post("/api/v1/session").json() == response.json()
    client.cookies.clear()
    client.post("/api/v1/session")
    assert client.cookies.get(COOKIE_NAME) != cookie
    assert session_db.scalar(select(func.count()).select_from(User)) == 2


@pytest.mark.parametrize(
    "tested,voice,no_preference,languages,completed,route",
    [
        (False, None, False, [], False, "/test"),
        (True, None, False, [], False, "/onboarding/voice"),
        (True, "talking", False, [], False, "/onboarding/languages"),
        (True, "both", False, [], False, "/onboarding/languages"),
        (True, "no_talking", False, [], False, "/onboarding/extra-preferences"),
        (True, "talking", True, [], False, "/onboarding/extra-preferences"),
        (True, "both", True, [], False, "/onboarding/extra-preferences"),
        (True, "talking", False, ["ko", "en"], False, "/onboarding/extra-preferences"),
        (True, "both", False, ["ja"], False, "/onboarding/extra-preferences"),
        (True, "no_talking", False, [], True, "/home"),
        (True, "talking", True, [], True, "/home"),
    ],
)
def test_resume_route(
    client, session_db, tested, voice, no_preference, languages, completed, route,
):
    client.post("/api/v1/session")
    user = session_db.get(User, read_identity(client.cookies.get(COOKIE_NAME), SECRET))
    user.initial_test_completed_at = datetime.now(timezone.utc) if tested else None
    user.voice_mode = voice
    user.language_no_preference = no_preference
    user.onboarding_completed = completed
    for language in languages:
        session_db.add(UserLanguagePreference(
            user_id=user.id, language=language, created_at=datetime.now(timezone.utc),
        ))
    session_db.commit()
    response = client.post("/api/v1/session")
    assert response.json() == {
        "initial_test_completed": tested,
        "onboarding_completed": completed,
        "next_route": route,
    }


@pytest.mark.parametrize("invalid", ["malformed", "raw_id", "tampered", "missing_user"])
def test_invalid_identity_creates_new_user(client, session_db, invalid):
    client.post("/api/v1/session")
    original = client.cookies.get(COOKIE_NAME)
    identity = read_identity(original, SECRET)
    cookies = {
        "malformed": "invalid",
        "raw_id": str(identity),
        "tampered": str(identity) + "." + "0" * 64,
        "missing_user": sign_identity(uuid4(), SECRET),
    }
    client.cookies.clear()
    client.cookies.set(COOKIE_NAME, cookies[invalid], domain="testserver.local")
    response = client.post(
        f"/api/v1/session?user_id={identity}", json={"user_id": str(identity)},
    )
    assert response.status_code == 200
    assert read_identity(client.cookies.get(COOKIE_NAME), SECRET) != identity
    assert session_db.scalar(select(func.count()).select_from(User)) == 2


def test_local_http_cookie_setting(client, monkeypatch):
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "false")
    response = client.post("/api/v1/session")
    assert "Secure" not in response.headers["set-cookie"]
    assert "HttpOnly" in response.headers["set-cookie"]


def test_missing_secret_fails_before_creating_user(client, session_db, monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", "")
    with pytest.raises(ValueError, match="SESSION_SECRET"):
        client.post("/api/v1/session")
    assert session_db.scalar(select(func.count()).select_from(User)) == 0


def test_session_cors():
    with TestClient(app) as client:
        response = client.options("/api/v1/session", headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        })
        assert response.status_code == 200
        assert response.headers["access-control-allow-credentials"] == "true"
        assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
        response = client.options("/api/v1/session", headers={
            "Origin": "https://untrusted.example",
            "Access-Control-Request-Method": "POST",
        })
        assert response.status_code == 400
        assert "access-control-allow-origin" not in response.headers
