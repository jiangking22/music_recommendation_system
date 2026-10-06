from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, SecretStr, StringConstraints

Username = Annotated[str, StringConstraints(min_length=6, max_length=20, pattern=r"^[A-Za-z0-9_]+$")]
Password = Annotated[SecretStr, Field(min_length=6, max_length=20)]


class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    username: Username
    password: Password
    remember: bool = False


class ChangePassword(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    old_password: Password
    new_password: Password


class PublicUser(BaseModel):
    user_id: str
    username: str


class AuthResponse(BaseModel):
    user: PublicUser
    session_id: str
    expires_at: datetime | None = None


class CsrfResponse(BaseModel):
    csrf_token: str


class SuccessResponse(BaseModel):
    status: str = "ok"
