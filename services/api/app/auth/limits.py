from redis import Redis
from redis.exceptions import RedisError

from app.auth.service import AuthError, digest
from app.infrastructure.config import get_settings

_COUNT = """
local n = redis.call('INCR', KEYS[1])
if n == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
return {n, redis.call('TTL', KEYS[1])}
"""


def limit_auth(redis: Redis, operation: str, source: str, username: str = "") -> None:
    settings = get_settings()
    limits = [(f"{operation}:source:{digest(source)}", settings.auth_register_source_limit
               if operation == "register" else settings.auth_login_source_limit)]
    if operation == "login":
        limits.append((f"login:account:{digest(username.lower())}", settings.auth_login_account_limit))
    try:
        for key, maximum in limits:
            count, ttl = redis.eval(_COUNT, 1, "auth:" + key, 900)
            if int(count) > maximum:
                raise AuthError("auth_rate_limited", 429, "Too many attempts. Please retry later.", max(1, int(ttl)))
    except RedisError as exc:
        raise AuthError("auth_unavailable", 503, "Account service unavailable. Please retry.", 2) from exc
