"""Run inside the API container after compose up --build --wait, in offline mode."""

import argparse
import json
from urllib.request import Request, urlopen
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.domain.embedding import embed_song
from app.infrastructure.cache import get_redis
from app.infrastructure.database import get_engine
from app.repository.embedding import similar_songs, store_song_embedding
from app.services.recommendation import local_catalog


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--web-url", default="http://web:3000")
    args = parser.parse_args()
    device = "smoke_" + uuid4().hex

    def api(path, body=None):
        request = Request("http://127.0.0.1:8000" + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Content-Type": "application/json", "X-Device-Id": device})
        with urlopen(request, timeout=40) as response:
            assert response.status == 200 and response.headers["X-Request-Id"]
            return json.load(response)

    with Session(get_engine()) as session:
        assert session.scalar(text("SELECT version_num FROM alembic_version")) == "0005_music_knowledge"
        assert session.scalar(text("SELECT extname FROM pg_extension WHERE extname='vector'")) == "vector"
        assert session.scalar(text("SELECT count(*) FROM music_knowledge_chunks")) == 4
        track = local_catalog()[0]
        vector = embed_song(track)
        store_song_embedding(session, track.canonical_key, vector)
        assert similar_songs(session, vector, 1)[0] == (track.canonical_key, 1.0)
    assert get_redis().ping()
    assert api("/health/ready")["status"] == "ok"
    with urlopen(args.web_url, timeout=10) as response:
        assert response.status == 200
    with urlopen(args.web_url + "/agent", timeout=10) as response:
        assert response.status == 200
    first = api("/v1/recommendations", {"seed": "calm jazz", "limit": 3})
    assert len(first["items"]) == 3 and first["sources"] == {}  # no business network
    feedback = api("/v1/feedback", {"track": first["items"][0]["track"], "value": "like"})
    assert feedback["value"] == "like"
    assert api("/v1/profile")["artists"]
    second = api("/v1/recommendations", {"seed": "calm jazz", "limit": 3})
    assert first["items"] != second["items"]
    chat = api("/v1/agent/chat", {"message": "推荐适合学习的歌", "device_id": device})
    assert chat["provider"] == "local" and chat["recommended_tracks"] and chat["citations"]
    followup = api("/v1/agent/chat", {"message": "再来几首", "device_id": device,
                                   "conversation_id": chat["conversation_id"]})
    assert followup["conversation_id"] == chat["conversation_id"]
    print(json.dumps({"event": "clean_start_smoke", "status": "ok", "checks": [
        "migrations", "pgvector_query", "redis", "readiness", "web", "recommendations", "feedback",
        "personalization", "local_agent", "rag", "conversation_resume"]}))


if __name__ == "__main__":
    main()
