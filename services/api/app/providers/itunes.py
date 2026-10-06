from collections.abc import Mapping

import httpx

from app.domain.music import (
    Album,
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
    artist_matches,
    nonempty,
    optional_object,
    require_list,
    safe_https_url,
)


def map_itunes_track(value: object) -> Track | None:
    item = optional_object(value)
    if item.get("wrapperType") != "track" or item.get("kind") != "song":
        return None
    track_id = nonempty(item.get("trackId"))
    title = nonempty(item.get("trackName"))
    artist_name = nonempty(item.get("artistName"))
    if not (track_id and title and artist_name):
        return None
    duration = item.get("trackTimeMillis")
    if duration is not None and (not isinstance(duration, int) or duration < 0):
        raise InvalidPayload("Invalid duration")
    album_name = nonempty(item.get("collectionName"))
    genre = nonempty(item.get("primaryGenreName"))
    return Track(
        title=title,
        artist=Artist(name=artist_name, provider_artist_id=nonempty(item.get("artistId"))),
        album=Album(name=album_name, provider_album_id=nonempty(item.get("collectionId"))) if album_name else None,
        duration_ms=duration,
        artwork_url=safe_https_url(item.get("artworkUrl100")),
        source=ProviderSource(provider="itunes", provider_track_id=track_id,
                              external_url=safe_https_url(item.get("trackViewUrl"))),
        genres=[genre] if genre else [],
        canonical_key=canonical_key(title, artist_name),
    )


class ITunesProvider(HTTPMusicProvider):
    name = "itunes"

    def __init__(self, client: httpx.Client | None = None, *, storefront: str = "US") -> None:
        if storefront not in {"US", "TW", "HK"}:
            raise ValueError("Unsupported Apple storefront")
        super().__init__(client)
        self.storefront = storefront

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(provider=self.name, search_tracks=True, search_artist_tracks=True,
                                    stability="documented", max_results=25)

    def _search(self, term: str, limit: int) -> list[Track]:
        term = self._bounded_query(term)
        payload: Mapping[str, object] = self._request(
            "GET", "https://itunes.apple.com/search",
            params={"term": term, "country": self.storefront, "media": "music", "entity": "song", "limit": limit},
        )
        items = require_list(payload.get("results"))
        tracks = [track for value in items[:limit] if (track := map_itunes_track(value))]
        return tracks

    def search_tracks(self, query: str, limit: int) -> ProviderResult:
        return self._execute(lambda: self._search(query, self._bounded_limit(limit)))

    def search_artist_tracks(self, artist: str, limit: int) -> ProviderResult:
        return self._execute(lambda: [track for track in self._search(artist, self._bounded_limit(limit))
                                      if artist_matches(track, artist)])
