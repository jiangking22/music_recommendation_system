from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.infrastructure.cache import get_redis
from app.infrastructure.database import get_session
from app.main import app
from app.repository.models import Base

PASSWORD = "a long password with spaces"
ORIGIN = "http://localhost:3000"


class FakeRedis:
    def __init__(self):
        self.counts = {}

    def eval(self, _script, _n, key, _window):
        self.counts[key] = self.counts.get(key, 0) + 1
        return [self.counts[key], 900]


@pytest.fixture
def auth_env(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'auth.db'}")
    Base.metadata.create_all(engine)

    def sessions():
        with Session(engine) as session:
            yield session

    redis = FakeRedis()
    app.dependency_overrides[get_session] = sessions
    app.dependency_overrides[get_redis] = lambda: redis
    with TestClient(app) as client:
        yield client, engine, redis
    app.dependency_overrides.clear()
    engine.dispose()


def csrf(client):
    response = client.get("/v1/auth/csrf")
    assert response.status_code == 200
    return {"Origin": ORIGIN, "X-CSRF-Token": response.json()["csrf_token"]}


def register(client, username="Listener"):
    return client.post("/v1/auth/register", headers=csrf(client),
                       json={"username": username, "password": PASSWORD})


def test_register_login_cookie_and_case_insensitive_uniqueness(auth_env):
    from app.repository.models import Account, LoginSession

    client, engine, _ = auth_env
    registered = register(client)
    assert registered.status_code == 201
    assert registered.json()["user"]["username"] == "Listener"
    assert datetime.fromisoformat(registered.json()["expires_at"]) > datetime.now(UTC)
    cookie = registered.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie
    assert client.get("/v1/auth/me").status_code == 200
    assert register(client, "listener").status_code == 409
    with Session(engine) as db:
        account = db.scalar(select(Account))
        assert account.password_hash.startswith("$argon2id$")
        assert PASSWORD not in account.password_hash
        login = db.scalar(select(LoginSession))
        assert login.token_digest != client.cookies["sonora_session"]
    assert client.post("/v1/auth/logout", headers=csrf(client)).status_code == 200
    assert client.get("/v1/auth/me").status_code == 401
    logged = client.post("/v1/auth/login", headers=csrf(client),
                         json={"username": "LISTENER", "password": PASSWORD, "remember": True})
    assert logged.status_code == 200
    assert "Max-Age=2592000" in logged.headers["set-cookie"]


def test_seven_character_password_register_login_and_duplicate_username(auth_env):
    client, _, _ = auth_env
    payload = {"username": "ShortPassword", "password": "seven_7"}
    assert client.post("/v1/auth/register", headers=csrf(client), json=payload).status_code == 201
    duplicate = client.post("/v1/auth/register", headers=csrf(client),
                            json=payload | {"username": "SHORTPASSWORD"})
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "username_taken"
    assert client.post("/v1/auth/logout", headers=csrf(client)).status_code == 200
    assert client.post("/v1/auth/login", headers=csrf(client), json=payload).status_code == 200
    changed = client.post("/v1/auth/change-password", headers=csrf(client),
                          json={"old_password": "seven_7", "new_password": "new_pwd"})
    assert changed.status_code == 200
    assert client.get("/v1/auth/me").status_code == 401
    assert client.post("/v1/auth/login", headers=csrf(client),
                       json=payload | {"password": "new_pwd"}).status_code == 200


def test_password_change_rejects_six_characters_without_revoking_session(auth_env):
    client, _, _ = auth_env
    assert register(client).status_code == 201
    response = client.post("/v1/auth/change-password", headers=csrf(client),
                           json={"old_password": PASSWORD, "new_password": "sixsix"})
    assert response.status_code == 422
    assert client.get("/v1/auth/me").status_code == 200


def test_admin_reset_accepts_seven_characters_and_rejects_six(auth_env):
    from app.auth.service import AuthError, reset_password

    client, engine, _ = auth_env
    assert register(client).status_code == 201
    with Session(engine) as db:
        reset_password(db, "listener", "reset_7")
    assert client.get("/v1/auth/me").status_code == 401
    with Session(engine) as db, pytest.raises(AuthError) as error:
        reset_password(db, "Listener", "sixsix")
    assert error.value.code == "validation_error"
    assert client.post("/v1/auth/login", headers=csrf(client),
                       json={"username": "Listener", "password": "reset_7"}).status_code == 200


@pytest.mark.parametrize("origin", ["*", "http://*", "https://*.example.com", "https://example.com/"])
def test_allowed_origins_require_exact_hostnames(origin):
    from pydantic import ValidationError

    from app.infrastructure.config import Settings

    with pytest.raises(ValidationError):
        Settings(database_url="sqlite+pysqlite:///:memory:", redis_url="redis://localhost:6379/0",
                 allowed_origins=origin)


def test_production_configuration_secure_cookies_and_disabled_documentation():
    import os
    import subprocess
    import sys

    environment = os.environ.copy() | {"APP_ENVIRONMENT": "production", "AUTH_COOKIE_SECURE": "false",
                                       "ALLOWED_ORIGINS": "https://sonora.example"}
    failed = subprocess.run([sys.executable, "-c", "import app.main"], env=environment,
                            capture_output=True, text=True, timeout=15, check=False)
    assert failed.returncode != 0 and "secure auth cookies" in failed.stderr
    environment["AUTH_COOKIE_SECURE"] = "true"
    program = """
from fastapi.testclient import TestClient
from app.main import app
with TestClient(app) as client:
    for path in ['/docs', '/redoc', '/openapi.json']:
        assert client.get(path).status_code == 404
    cookie = client.get('/v1/auth/csrf').headers['set-cookie']
    assert 'Secure' in cookie and 'HttpOnly' in cookie and 'SameSite=lax' in cookie
"""
    passed = subprocess.run([sys.executable, "-c", program], env=environment,
                            capture_output=True, text=True, timeout=15, check=False)
    assert passed.returncode == 0


def test_invalid_login_is_generic_and_csrf_origin_required(auth_env):
    client, _, _ = auth_env
    register(client)
    bodies = []
    for username in ["Listener", "Unknown"]:
        response = client.post("/v1/auth/login", headers=csrf(client),
                               json={"username": username, "password": "wrong password long"})
        assert response.status_code == 401
        bodies.append(response.json())
    assert bodies[0] == bodies[1]
    payload = {"username": "Another", "password": PASSWORD}
    assert client.post("/v1/auth/register", json=payload).status_code == 403
    headers = csrf(client) | {"Origin": "https://evil.example"}
    assert client.post("/v1/auth/register", headers=headers, json=payload).status_code == 403


def test_change_password_and_admin_reset_revoke_all_sessions(auth_env):
    from app.auth.service import reset_password

    client, engine, _ = auth_env
    register(client)
    old_cookie = client.cookies["sonora_session"]
    result = client.post("/v1/auth/change-password", headers=csrf(client),
                         json={"old_password": PASSWORD, "new_password": "new long password here"})
    assert result.status_code == 200
    client.cookies.set("sonora_session", old_cookie)
    assert client.get("/v1/auth/me").status_code == 401
    with Session(engine) as db:
        reset_password(db, "listener", PASSWORD)
    assert client.post("/v1/auth/login", headers=csrf(client),
                       json={"username": "Listener", "password": PASSWORD}).status_code == 200
    with Session(engine) as db:
        reset_password(db, "Listener", "a different long password")
    assert client.get("/v1/auth/me").status_code == 401


def test_expired_session_rate_limit_and_redis_failure(auth_env):
    from app.repository.models import LoginSession

    client, engine, redis = auth_env
    register(client)
    with Session(engine) as db:
        row = db.scalar(select(LoginSession))
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    assert client.get("/v1/auth/me").status_code == 401
    for _ in range(11):
        limited = client.post("/v1/auth/login", headers=csrf(client),
                              json={"username": "Unknown", "password": PASSWORD})
    assert limited.status_code == 429
    assert int(limited.headers["retry-after"]) > 0

    def unavailable(*_args):
        raise ConnectionError()

    redis.eval = unavailable
    assert client.post("/v1/auth/register", headers=csrf(client),
                       json={"username": "NextUser", "password": PASSWORD}).status_code == 503


@pytest.mark.parametrize("username,password", [("ab", PASSWORD), ("a-b", PASSWORD),
                         ("valid", "short"), ("valid", "sixsix"), ("valid", "x" * 129)])
def test_registration_validation(auth_env, username, password):
    client, _, _ = auth_env
    assert client.post("/v1/auth/register", headers=csrf(client),
                       json={"username": username, "password": password}).status_code == 422


def test_password_counts_unicode_characters_and_preserves_spaces(auth_env):
    client, _, _ = auth_env
    password = " 🎵" * 50
    payload = {"username": "UnicodeUser", "password": password}
    assert client.post("/v1/auth/register", headers=csrf(client), json=payload).status_code == 201
    assert client.post("/v1/auth/login", headers=csrf(client), json=payload).status_code == 200
