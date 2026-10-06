import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_auth import PASSWORD, csrf, register
from test_auth import auth_env as auth_env  # noqa: PLC0414

from app.agent.providers import LocalLLMProvider, get_llm_provider
from app.main import app
from app.providers.registry import ProviderRegistry, get_provider_registry
from app.repository.models import DeviceUser, TrackFeedback
from app.services.recommendation import local_catalog


@pytest.mark.parametrize("method,path,body", [
    ("GET", "/v1/profile", None), ("GET", "/v1/providers", None),
    ("GET", "/v1/providers/health", None), ("GET", "/v1/tracks/search?q=jazz", None),
    ("GET", "/v1/device", None), ("GET", "/v1/mcp/tools", None),
    ("POST", "/v1/recommendations", {"seed": "jazz"}),
    ("POST", "/v1/feedback", {}), ("POST", "/v1/recordings/resolve", {"seed": "jazz"}),
    ("POST", "/v1/recommendations/discover", {"seed": "jazz"}),
    ("POST", "/v1/recommendations/identify-original", {}),
    ("POST", "/v1/agent/chat", {"message": "hi"}),
    ("POST", "/v1/agent/chat/stream", {"message": "hi"}),
    ("POST", "/v1/mcp/tools/call", {}),
])
def test_every_business_route_requires_real_login(auth_env, method, path, body):
    client, _, _ = auth_env
    result = client.request(method, path, json=body, headers={"X-Device-Id": "device_1234567890"})
    assert result.status_code == 401
    assert result.json()["error"]["code"] == "authentication_required"


def business_headers(client):
    return csrf(client) | {"X-Session-Id": client.get("/v1/auth/me").json()["session_id"]}


def test_preferences_follow_account_and_anonymous_data_is_not_claimed(auth_env):
    from app.repository.models import AccountFeedback, AccountProfile

    client, engine, _ = auth_env
    app.dependency_overrides[get_provider_registry] = lambda: ProviderRegistry([])
    with Session(engine) as db:
        db.add(DeviceUser(device_id="device_1234567890"))
        db.add(TrackFeedback(device_id="device_1234567890", track_key="old", value="like",
                             artist="old artist", genres=[], tags=[]))
        db.commit()
    user = register(client).json()["user"]
    headers = business_headers(client) | {"X-Device-Id": "device_1234567890"}
    assert client.get("/v1/profile", headers=headers).json()["recent_feedback"] == []
    track = local_catalog()[0].model_dump(mode="json")
    assert client.post("/v1/feedback", json={"track": track, "value": "like"}, headers=headers).status_code == 200
    profile = client.get("/v1/profile", headers=headers).json()
    assert len(profile["recent_feedback"]) == 1
    first_cookie = client.cookies["sonora_session"]
    client.cookies.clear()
    logged = client.post("/v1/auth/login", headers=csrf(client),
                         json={"username": "listener", "password": PASSWORD})
    assert logged.status_code == 200
    assert client.cookies["sonora_session"] != first_cookie
    assert client.get("/v1/profile", headers=business_headers(client)).json() == profile
    client.cookies.clear()
    register(client, "OtherUser")
    assert client.get("/v1/profile", headers=business_headers(client)).json()["recent_feedback"] == []
    with Session(engine) as db:
        assert db.scalar(select(AccountFeedback)).user_id == user["user_id"]
        assert db.get(AccountProfile, user["user_id"]).embedding is not None
        assert len(db.scalars(select(TrackFeedback)).all()) == 1


def test_agent_is_bound_to_account_and_login_session_and_rejects_owner_override(auth_env):
    client, _, _ = auth_env
    app.dependency_overrides[get_provider_registry] = lambda: ProviderRegistry([])
    app.dependency_overrides[get_llm_provider] = LocalLLMProvider
    register(client)
    first = client.post("/v1/agent/chat", json={"message": "推荐学习音乐"}, headers=business_headers(client))
    assert first.status_code == 200
    body = {"message": "再来几首", "conversation_id": first.json()["conversation_id"]}
    assert client.post("/v1/agent/chat", json=body, headers=business_headers(client)).status_code == 200
    assert client.post("/v1/agent/chat", json=body | {"device_id": "device_1234567890"},
                       headers=business_headers(client)).status_code == 422
    client.cookies.clear()
    client.post("/v1/auth/login", headers=csrf(client), json={"username": "Listener", "password": PASSWORD})
    assert client.post("/v1/agent/chat", json=body, headers=business_headers(client)).status_code == 404
    client.cookies.clear()
    register(client, "SomeoneElse")
    assert client.post("/v1/agent/chat", json=body, headers=business_headers(client)).status_code == 404


def test_business_writes_require_csrf_and_stale_tab_context_is_rejected(auth_env):
    client, _, _ = auth_env
    register(client)
    old = business_headers(client)
    assert client.post("/v1/recommendations", json={"seed": "jazz"}).status_code == 403
    client.cookies.clear()
    register(client, "AnotherUser")
    assert client.get("/v1/profile", headers=old).status_code == 401
    assert client.get("/v1/device", headers=business_headers(client)).status_code == 410


def test_concurrent_feedback_keeps_both_tracks_and_the_complete_profile(auth_env):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from app.repository.feedback import save_feedback
    from app.repository.models import AccountFeedback, AccountProfile

    client, engine, _ = auth_env
    user = register(client).json()["user"]["user_id"]
    tracks = local_catalog()[:2]
    barrier = Barrier(2)

    def write(track):
        with Session(engine) as db:
            barrier.wait(timeout=5)
            save_feedback(db, user, track, "like")

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(write, tracks))
    with Session(engine) as db:
        assert len(db.scalars(select(AccountFeedback).where(AccountFeedback.user_id == user)).all()) == 2
        profile = db.get(AccountProfile, user)
        assert len(profile.artist_affinity) == 2


def test_auth_and_business_logs_never_include_credentials(auth_env, caplog):
    client, _, _ = auth_env
    register(client, "PrivateUsername")
    token = client.cookies["sonora_session"]
    headers = business_headers(client)
    client.get("/v1/profile", headers=headers)
    response = client.post("/v1/auth/login", headers=csrf(client),
                           json={"username": "PrivateUsername", "password": "wrong password value"})
    assert response.status_code == 401
    assert PASSWORD not in caplog.text
    assert "PrivateUsername" not in caplog.text
    assert token not in caplog.text
    assert headers["X-CSRF-Token"] not in caplog.text
