import hashlib
import secrets
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.observability.events import emit
from app.repository.models import Account, LoginSession

PASSWORD_HASHER = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
_dummy_hash = PASSWORD_HASHER.hash(secrets.token_urlsafe(32))
_password_slots = threading.BoundedSemaphore(4)


class AuthError(Exception):
    def __init__(self, code: str, status: int, message: str, retry_after: int | None = None):
        self.code, self.status, self.message, self.retry_after = code, status, message, retry_after


@dataclass(frozen=True)
class Identity:
    user_id: str
    username: str
    session_id: str
    expires_at: datetime | None = None


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@contextmanager
def password_work():
    if not _password_slots.acquire(blocking=False):
        raise AuthError("auth_busy", 503, "Account service is busy. Please retry.", 1)
    try:
        yield
    finally:
        _password_slots.release()


def hash_password(password: str) -> str:
    if not 15 <= len(password) <= 128:
        raise AuthError("validation_error", 422, "Password must have 15–128 characters.")
    with password_work():
        return PASSWORD_HASHER.hash(password)


def verify_password(encoded: str | None, password: str) -> bool:
    with password_work():
        try:
            valid = PASSWORD_HASHER.verify(encoded or _dummy_hash, password)
            return bool(encoded and valid)
        except (VerificationError, InvalidHashError):
            return False


def issue_session(db: Session, account: Account, remember: bool) -> tuple[Identity, str, int]:
    token = secrets.token_urlsafe(32)
    lifetime = 30 * 86400 if remember else 86400
    row = LoginSession(session_id=str(uuid4()), user_id=account.user_id, token_digest=digest(token),
                       expires_at=datetime.now(UTC) + timedelta(seconds=lifetime))
    db.add(row)
    return Identity(account.user_id, account.username, row.session_id, row.expires_at), token, lifetime


def read_identity(db: Session, token: str | None) -> Identity:
    if not token or len(token) > 128:
        raise AuthError("authentication_required", 401, "Please sign in.")
    row = db.execute(select(LoginSession, Account).join(Account).where(
        LoginSession.token_digest == digest(token), LoginSession.revoked_at.is_(None),
        LoginSession.expires_at > datetime.now(UTC))).first()
    if not row:
        raise AuthError("authentication_required", 401, "Please sign in.")
    login, account = row
    expires_at = login.expires_at if login.expires_at.tzinfo else login.expires_at.replace(tzinfo=UTC)
    return Identity(account.user_id, account.username, login.session_id, expires_at)


def reset_password(db: Session, username: str, password: str) -> None:
    encoded = hash_password(password)
    with db.begin():
        account = db.scalar(select(Account).where(Account.username_key == username.lower()).with_for_update())
        if not account:
            raise AuthError("account_not_found", 404, "Account not found.")
        account.password_hash = encoded
        db.execute(update(LoginSession).where(LoginSession.user_id == account.user_id,
                   LoginSession.revoked_at.is_(None)).values(revoked_at=datetime.now(UTC)))
    emit("auth_event", operation="admin_reset", status="ok")
