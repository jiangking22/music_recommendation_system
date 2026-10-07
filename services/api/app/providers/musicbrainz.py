"""Recording metadata only; MusicBrainz is not a streaming service."""

from threading import Lock
from time import monotonic, sleep
from uuid import UUID

from app.domain.music import (
    Artist,
    ProviderCapabilities,
    ProviderResult,
    ProviderSource,
    Track,
    canonical_key,
)
from app.providers.base import (
    HTTPMusicProvider,
    InvalidPayload,
    nonempty,
    optional_object,
    require_list,
)

_rate_lock = Lock()
_last_request = 0.0


def map_recording(value: object) -> Track | None:
    item = optional_object(value)
    identifier, title = nonempty(item.get("id")), nonempty(item.get("title"))
    credits = require_list(item.get("artist-credit", []))
    names = [name for credit in credits
             if (name := nonempty(optional_object(optional_object(credit).get("artist")).get("name")))]
    if not identifier or not title or not names:
        return None
    try:
        UUID(identifier)
    except ValueError as error:
        raise InvalidPayload("Invalid recording ID") from error
    artist = ", ".join(names)
    disambiguation = nonempty(item.get("disambiguation")) or ""
    tags = [kind for kind in ("live", "cover", "karaoke", "instrumental", "remix")
            if kind in disambiguation.casefold()]
    return Track(title=title, artist=Artist(name=artist), duration_ms=item.get("length"), tags=tags,
                 source=ProviderSource(provider="musicbrainz", provider_track_id=identifier,
                                       external_url=f"https://musicbrainz.org/recording/{identifier}"),
                 canonical_key=canonical_key(title, artist))


class MusicBrainzProvider(HTTPMusicProvider):
    name = "musicbrainz"

    def capabilities(self):
        return ProviderCapabilities(provider=self.name, search_tracks=True, search_artist_tracks=True,
                                    stability="documented", max_results=25)

    def _get(self, path, params):
        global _last_request
        # One request/second across instances and request workers, including lookups.
        with _rate_lock:
            sleep(max(0, 1 - (monotonic() - _last_request)))
            _last_request = monotonic()
            return self._request("GET", f"https://musicbrainz.org/ws/2/recording/{path}", params=params,
                headers={"User-Agent": "Sonora/1.0 (https://github.com/jiangking22/sonora)"})

    def search_tracks(self, query: str, limit: int) -> ProviderResult:
        def fetch():
            # Quote all input; do not allow a user query to introduce Lucene operators.
            text = self._bounded_query(query).replace("\\", "\\\\").replace('"', '\\"')
            payload = self._get("", {"query": f'"{text}"', "fmt": "json", "limit": self._bounded_limit(limit)})
            return [track for item in require_list(payload.get("recordings"))[:limit]
                    if (track := map_recording(item))]
        return self._execute(fetch)

    def lookup_track(self, identifier: str) -> ProviderResult:
        def fetch():
            path = str(UUID(identifier))
            track = map_recording(self._get(path, {"inc": "artists", "fmt": "json"}))
            if track and track.source.provider_track_id != path:
                raise InvalidPayload("Recording ID mismatch")
            return [track] if track else []
        return self._execute(fetch)

    def search_recording(self, title: str, artist: str, limit: int) -> ProviderResult:
        def quote(value):
            return value.replace("\\", "\\\\").replace('"', '\\"')
        def fetch():
            payload = self._get("", {"query": f'recording:"{quote(title[:120])}" AND artist:"{quote(artist[:200])}"',
                                     "fmt": "json", "limit": self._bounded_limit(limit)})
            return [track for item in require_list(payload.get("recordings"))[:limit]
                    if (track := map_recording(item))]
        return self._execute(fetch)

    def search_artist_tracks(self, artist: str, limit: int) -> ProviderResult:
        return self.search_tracks(artist, limit)
