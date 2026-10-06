import secrets
from datetime import UTC, datetime
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, Request, Response
from redis import Redis
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    CurrentIdentity,
    check_csrf,
)
from app.auth.limits import limit_auth
from app.auth.schemas import (
    AuthResponse,
    ChangePassword,
    Credentials,
    CsrfResponse,
    PublicUser,
    SuccessResponse,
)
from app.auth.service import (
    AuthError,
    Identity,
    hash_password,
    issue_session,
    verify_password,
)
from app.infrastructure.cache import get_redis
from app.infrastructure.config import get_settings
from app.infrastructure.database import get_session
from app.observability.events import emit
from app.repository.models import Account, LoginSession

router = APIRouter(prefix="/v1/auth", tags=["auth"])
Database = Annotated[Session, Depends(get_session)]
Cache = Annotated[Redis, Depends(get_redis)]


def cookie(response: Response, name: str, value: str, age: int) -> None:
    response.set_cookie(name, value, max_age=age, path="/", httponly=True,
                        secure=get_settings().auth_cookie_secure, samesite="lax")
    response.headers["Cache-Control"] = "no-store"


def public(identity: Identity) -> AuthResponse:
    return AuthResponse(user=PublicUser(user_id=identity.user_id, username=identity.username),
                        session_id=identity.session_id)


def establish(response: Response, db: Session, account: Account, remember: bool) -> AuthResponse:
    identity, token, age = issue_session(db, account, remember)
    cookie(response, SESSION_COOKIE, token, age)
    cookie(response, CSRF_COOKIE, secrets.token_urlsafe(32), age)
    return public(identity)


@router.get("/csrf", response_model=CsrfResponse)
def csrf(request: Request, response: Response) -> CsrfResponse:
    # A host-only HttpOnly double-submit cookie plus strict Origin validation protects pre-login forms.
    origin = request.headers.get("origin")
    if origin and origin not in get_settings().allowed_origins_list:
        raise AuthError("csrf_invalid", 403, "Origin unavailable.")
    token = request.cookies.get(CSRF_COOKIE)
    if not token or not 32 <= len(token) <= 128:
        token = secrets.token_urlsafe(32)
        cookie(response, CSRF_COOKIE, token, 30 * 86400)
    response.headers["Cache-Control"] = "no-store"
    return CsrfResponse(csrf_token=token)


@router.post("/register", response_model=AuthResponse, status_code=201, dependencies=[Depends(check_csrf)])
def register(payload: Credentials, request: Request, response: Response, db: Database, redis: Cache):
    limit_auth(redis, "register", request.client.host if request.client else "unknown")
    encoded = hash_password(payload.password.get_secret_value())
    try:
        with db.begin():
            account = Account(user_id=str(uuid4()), username=payload.username,
                              username_key=payload.username.lower(), password_hash=encoded)
            db.add(account)
            db.flush()
            result = establish(response, db, account, payload.remember)
    except IntegrityError as exc:
        raise AuthError("username_taken", 409, "Username is already taken.") from exc
    emit("auth_event", operation="register", status="ok")
    return result


@router.post("/login", response_model=AuthResponse, dependencies=[Depends(check_csrf)])
def login(payload: Credentials, request: Request, response: Response, db: Database, redis: Cache):
    limit_auth(redis, "login", request.client.host if request.client else "unknown", payload.username)
    # Serialize login with password changes/resets so an old password cannot create a session after revocation.
    with db.begin():
        account = db.scalar(select(Account).where(Account.username_key == payload.username.lower()).with_for_update())
        if not verify_password(account.password_hash if account else None, payload.password.get_secret_value()):
            emit("auth_event", operation="login", status="invalid_credentials")
            raise AuthError("invalid_credentials", 401, "Username or password is incorrect.")
        result = establish(response, db, account, payload.remember)
    emit("auth_event", operation="login", status="ok")
    return result


@router.get("/me", response_model=AuthResponse)
def me(identity: CurrentIdentity, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return public(identity)


@router.post("/logout", response_model=SuccessResponse, dependencies=[Depends(check_csrf)])
def logout(identity: CurrentIdentity, db: Database, response: Response):
    with db.begin():
        db.execute(update(LoginSession).where(LoginSession.session_id == identity.session_id)
                   .values(revoked_at=datetime.now(UTC)))
    for name in (SESSION_COOKIE, CSRF_COOKIE):
        response.delete_cookie(name, path="/", httponly=True, secure=get_settings().auth_cookie_secure, samesite="lax")
    response.headers["Cache-Control"] = "no-store"
    emit("auth_event", operation="logout", status="ok")
    return SuccessResponse()


@router.post("/change-password", response_model=SuccessResponse, dependencies=[Depends(check_csrf)])
def change_password(payload: ChangePassword, identity: CurrentIdentity, db: Database, response: Response):
    with db.begin():
        account = db.scalar(select(Account).where(Account.user_id == identity.user_id).with_for_update())
        if not verify_password(account.password_hash, payload.old_password.get_secret_value()):
            raise AuthError("invalid_credentials", 401, "Username or password is incorrect.")
        account.password_hash = hash_password(payload.new_password.get_secret_value())
        db.execute(update(LoginSession).where(LoginSession.user_id == identity.user_id,
                   LoginSession.revoked_at.is_(None)).values(revoked_at=datetime.now(UTC)))
    for name in (SESSION_COOKIE, CSRF_COOKIE):
        response.delete_cookie(name, path="/", httponly=True, secure=get_settings().auth_cookie_secure, samesite="lax")
    emit("auth_event", operation="change_password", status="ok")
    return SuccessResponse()
