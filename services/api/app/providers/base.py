import json
import re
from collections.abc import Callable, Mapping
from ipaddress import ip_address
from typing import Protocol
from urllib.parse import urlparse

import httpx
from pydantic import ValidationError

from app.domain.music import (
    ProviderCapabilities,
    ProviderError,
    ProviderHealth,
    ProviderResult,
    Track,
)
from app.observability.events import correlation_headers

MAX_RESULTS = 25
MAX_RESPONSE_BYTES = 1_000_000
REQUEST_TIMEOUT = httpx.Timeout(4.0, connect=2.0)


class MusicProvider(Protocol):
    name: str

    def search_tracks(self, query: str, limit: int) -> ProviderResult: ...

    def search_artist_tracks(self, artist: str, limit: int) -> ProviderResult: ...

    def health(self) -> ProviderHealth: ...

    def capabilities(self) -> ProviderCapabilities: ...


class InvalidPayload(Exception):
    pass


def require_object(value: object) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise InvalidPayload("Expected object")
    return value


def require_list(value: object) -> list[object]:
    if not isinstance(value, list):
        raise InvalidPayload("Expected list")
    return value


def optional_object(value: object) -> Mapping[str, object]:
    return value if isinstance(value, dict) else {}


def nonempty(value: object) -> str | None:
    if isinstance(value, (str, int)) and str(value).strip():
        return str(value).strip()
    return None


def safe_https_url(value: object) -> str | None:
    url = nonempty(value)
    if url is None:
        return None
    try:
        parsed = urlparse(url)
        if (len(url) > 2048 or parsed.scheme != "https" or not parsed.hostname
                or parsed.username or parsed.password or parsed.hostname.rstrip(".") == "localhost"):
            return None
        try:
            if not ip_address(parsed.hostname).is_global:
                return None
        except ValueError:  # hostname: these display URLs are never fetched by the server.
            pass
        return url
    except ValueError:
        return None


class HTTPMusicProvider:
    name: str

    def __init__(self, client: httpx.Client | None = None) -> None:
        self.client = client or httpx.Client(follow_redirects=False, trust_env=False)
        self._health = ProviderHealth(status="unknown")

    def health(self) -> ProviderHealth:
        return self._health.model_copy(deep=True)

    def _request(self, method: str, url: str, *, jsonp: bool = False, **kwargs: object) -> Mapping[str, object]:
        kwargs["headers"] = {**kwargs.get("headers", {}), **correlation_headers()}
        with self.client.stream(method, url, timeout=REQUEST_TIMEOUT, **kwargs) as response:
            response.raise_for_status()
            chunks = bytearray()
            for chunk in response.iter_bytes():
                chunks.extend(chunk)
                if len(chunks) > MAX_RESPONSE_BYTES:
                    raise InvalidPayload("Response too large")
        try:
            body = chunks.decode("utf-8-sig")
            if jsonp:
                match = re.fullmatch(r"\s*[\w.]+\((.*)\)\s*;?\s*", body, flags=re.DOTALL)
                if match:
                    body = match.group(1)
            return require_object(json.loads(body))
        except (ValueError, UnicodeDecodeError) as exc:
            raise InvalidPayload("Invalid JSON") from exc

    def _execute(self, fetch: Callable[[], list[Track]]) -> ProviderResult:
        try:
            tracks = fetch()
            result = ProviderResult(provider=self.name, tracks=tracks)
            self._health = ProviderHealth(status="available")
            return result
        except httpx.TimeoutException:
            code = "timeout"
        except (httpx.HTTPError, OSError):
            code = "upstream_error"
        except (InvalidPayload, ValidationError, ValueError, TypeError, KeyError):
            code = "invalid_payload"
        error = ProviderError(code=code, message=f"{self.name} provider {code}.")
        self._health = ProviderHealth(status="degraded", last_error=error)
        return ProviderResult(provider=self.name, error=error)

    def _bounded_limit(self, limit: int) -> int:
        if not 1 <= limit <= MAX_RESULTS:
            raise ValueError("limit must be between 1 and 25")
        return limit

    def _bounded_query(self, query: str) -> str:
        query = query.strip()
        if not 1 <= len(query) <= 120:
            raise ValueError("query must be between 1 and 120 characters")
        return query


def artist_matches(track: Track, artist: str) -> bool:
    return track.artist.name.casefold().strip() == artist.casefold().strip()
