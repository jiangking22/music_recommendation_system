import secrets
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.auth.service import AuthError, Identity, digest, read_identity
from app.infrastructure.config import get_settings
from app.infrastructure.database import get_session

SESSION_COOKIE = "sonora_session"
CSRF_COOKIE = "sonora_csrf"


def check_csrf(request: Request) -> None:
    origin = request.headers.get("origin")
    cookie = request.cookies.get(CSRF_COOKIE, "")
    header = request.headers.get("x-csrf-token", "")
    if (origin not in get_settings().allowed_origins_list or not 32 <= len(cookie) <= 128 or
            not secrets.compare_digest(digest(cookie), digest(header))):
        raise AuthError("csrf_invalid", 403, "Request verification failed. Please reload.")


def current_identity(request: Request, db: Annotated[Session, Depends(get_session)]) -> Identity:
    # Use a separate short-lived transaction so feedback owns its write transaction.
    with Session(db.get_bind()) as auth_db:
        identity = read_identity(auth_db, request.cookies.get(SESSION_COOKIE))
    expected = request.headers.get("x-session-id")
    if expected and expected != identity.session_id:
        raise AuthError("session_changed", 401, "Session changed. Please sign in again.")
    request.state.identity = identity
    return identity


CurrentIdentity = Annotated[Identity, Depends(current_identity)]


def business_csrf(request: Request) -> None:
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        check_csrf(request)
