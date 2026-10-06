"""Verify account feedback serialization and vectors in a disposable PostgreSQL database."""

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.embedding import embed_user
from app.infrastructure.database import get_engine
from app.repository.feedback import load_profile, save_feedback
from app.repository.models import (
    Account,
    AccountFeedback,
    AccountProfile,
    TrackFeedback,
)
from app.services.recommendation import local_catalog


def main():
    engine = get_engine()
    assert engine.dialect.name == "postgresql", "This check requires PostgreSQL."
    user_id = str(uuid4())
    username = "pg_" + uuid4().hex[:20]
    with Session(engine) as db:
        archived = db.scalar(select(func.count()).select_from(TrackFeedback))
        db.add(Account(user_id=user_id, username=username,
                       username_key=username, password_hash="unused-test-account"))
        db.commit()
    tracks = local_catalog()[:2]
    barrier = Barrier(2)

    def write(track):
        with Session(engine) as db:
            barrier.wait(timeout=5)
            save_feedback(db, user_id, track, "like")

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(write, tracks))
    with Session(engine) as db:
        rows = db.scalars(select(AccountFeedback).where(AccountFeedback.user_id == user_id)).all()
        assert len(rows) == 2
        profile = db.get(AccountProfile, user_id)
        assert len(profile.artist_affinity) == 2
        expected = embed_user(load_profile(db, user_id))
        assert profile.embedding is not None
        assert all(abs(a - b) < 1e-6 for a, b in zip(profile.embedding, expected, strict=True))
        assert db.scalar(select(func.count()).select_from(TrackFeedback)) == archived
    print(json.dumps({"event": "account_postgres_check", "status": "ok",
                      "checks": ["concurrent_feedback", "account_vector", "anonymous_archive"]}))


if __name__ == "__main__":
    main()
