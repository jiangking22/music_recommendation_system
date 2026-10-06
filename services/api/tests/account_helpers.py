from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.repository.models import Account, LoginSession

TEST_USER = "account_test"
TEST_SESSION = "session_test"


def seed_account(engine, user_id=TEST_USER, session_id=TEST_SESSION):
    with Session(engine) as db:
        if not db.get(Account, user_id):
            db.add(Account(user_id=user_id, username=user_id, username_key=user_id,
                           password_hash="unused-subsystem-test-hash"))
            db.flush()
        if not db.get(LoginSession, session_id):
            db.add(LoginSession(session_id=session_id, user_id=user_id, token_digest=session_id,
                       expires_at=datetime.now(UTC) + timedelta(days=1)))
        db.commit()
