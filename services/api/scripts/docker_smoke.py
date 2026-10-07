"""Run inside the API container after Compose starts, using offline providers and a local Agent."""

import argparse
import json
import secrets
from uuid import uuid4

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.domain.embedding import embed_song
from app.infrastructure.cache import get_redis
from app.infrastructure.config import get_settings
from app.infrastructure.database import get_engine
from app.repository.embedding import similar_songs, store_song_embedding
from app.services.recommendation import local_catalog


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--web-url", default="http://web:3000")
    args = parser.parse_args()
    settings = get_settings()
    assert not settings.enable_music_providers and settings.llm_provider == "local", "Use an isolated offline stack."
    origin = settings.allowed_origins_list[0]
    username = "smoke_" + uuid4().hex[:14]
    password = secrets.token_urlsafe(15)
    with Session(get_engine()) as db:
        assert db.scalar(text("SELECT version_num FROM alembic_version")) == "0009_candidate_pool"
        assert db.scalar(text("SELECT extname FROM pg_extension WHERE extname='vector'")) == "vector"
        assert db.scalar(text("SELECT count(*) FROM music_knowledge_chunks")) == 4
        track = local_catalog()[0]
        vector = embed_song(track)
        store_song_embedding(db, track.canonical_key, vector)
        assert similar_songs(db, vector, 1)[0] == (track.canonical_key, 1.0)
    assert get_redis().ping()
    with httpx.Client(trust_env=False, timeout=10) as public:
        assert public.get("http://127.0.0.1:8000/health/ready").json()["status"] == "ok"
        assert public.get("http://127.0.0.1:8000/v1/profile").status_code == 401
        assert public.get(args.web_url).status_code == 200
        assert public.get(args.web_url + "/agent").status_code == 200
        assert public.get(args.web_url + "/api/v1/profile").status_code == 401
        assert public.post(args.web_url + "/api/v1/agent/chat/stream", json={"message": "hi"}).status_code == 401

    def request(client, path, body=None, expected=200):
        headers = {"Origin": origin}
        if body is not None:
            csrf = client.get("/api/v1/auth/csrf")
            assert csrf.status_code == 200
            headers["X-CSRF-Token"] = csrf.json()["csrf_token"]
        response = client.request("GET" if body is None else "POST", "/api/v1" + path,
                                  json=body, headers=headers)
        assert response.status_code == expected, (path, response.status_code)
        assert response.headers["X-Request-Id"] and response.headers["cache-control"] == "no-store"
        return response.json()

    with httpx.Client(base_url=args.web_url, timeout=70, trust_env=False) as first_device, \
            httpx.Client(base_url=args.web_url, timeout=70, trust_env=False) as second_device:
        credentials = {"username": username, "password": password}
        registered = request(first_device, "/auth/register", credentials, 201)
        assert first_device.cookies.get("sonora_session") and first_device.cookies.get("sonora_csrf")
        first_device.headers["X-Session-Id"] = registered["session_id"]
        assert request(first_device, "/profile")["recent_feedback"] == []
        first = request(first_device, "/recommendations", {"seed": "calm jazz", "limit": 3})
        assert len(first["items"]) == 3 and first["sources"] == {}
        feedback = request(first_device, "/feedback", {"track": first["items"][0]["track"], "value": "like"})
        assert feedback["value"] == "like"
        profile = request(first_device, "/profile")
        assert profile["artists"]
        second = request(first_device, "/recommendations", {"seed": "calm jazz", "limit": 3})
        assert first["items"] != second["items"]
        logged = request(second_device, "/auth/login", credentials | {"remember": True})
        second_device.headers["X-Session-Id"] = logged["session_id"]
        assert logged["session_id"] != registered["session_id"]
        assert request(second_device, "/profile") == profile
        chat = request(first_device, "/agent/chat", {"message": "推荐适合学习的歌"})
        assert chat["provider"] == "local" and chat["recommended_tracks"] and chat["citations"]
        followup = {"message": "再来几首", "conversation_id": chat["conversation_id"]}
        assert request(first_device, "/agent/chat", followup)["conversation_id"] == chat["conversation_id"]
        request(second_device, "/agent/chat", followup, 404)
        csrf = first_device.get("/api/v1/auth/csrf").json()["csrf_token"]
        with first_device.stream("POST", "/api/v1/agent/chat/stream", json={"message": "推荐爵士音乐"},
                                 headers={"Origin": origin, "X-CSRF-Token": csrf}) as stream:
            assert stream.status_code == 200 and "text/event-stream" in stream.headers["content-type"]
            content = "".join(stream.iter_text())
            assert "event: done" in content and "event: error" not in content
        request(first_device, "/auth/logout", {})
        request(first_device, "/profile", expected=401)
        # Another account never inherits the first account's preferences.
        other = request(first_device, "/auth/register", credentials | {"username": "other_" + uuid4().hex[:14]}, 201)
        first_device.headers["X-Session-Id"] = other["session_id"]
        assert request(first_device, "/profile")["recent_feedback"] == []
        request(first_device, "/agent/chat", followup, 404)
    print(json.dumps({"event": "clean_start_smoke", "status": "ok", "checks": [
        "migrations", "pgvector_query", "redis", "readiness", "web", "anonymous_401", "register_login",
        "cookie_csrf_proxy", "portable_preferences", "account_isolation", "local_agent", "rag",
        "login_session_isolation", "sse_proxy", "logout"]}))


if __name__ == "__main__":
    main()
