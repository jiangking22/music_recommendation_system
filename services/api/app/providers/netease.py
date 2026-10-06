import json
from collections.abc import Mapping

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


def map_netease_track(value: object) -> Track | None:
    item = optional_object(value)
    track_id = nonempty(item.get("id"))
    title = nonempty(item.get("name"))
    people = item.get("artists", item.get("ar", []))
    if not isinstance(people, list):
        raise InvalidPayload("Invalid artists")
    artists = [optional_object(person) for person in people]
    names = [name for person in artists if (name := nonempty(person.get("name")))]
    if not (track_id and title and names):
        return None
    artist_name = ", ".join(names)
    album = optional_object(item.get("album", item.get("al")))
    album_name = nonempty(album.get("name"))
    duration = item.get("duration", item.get("dt"))
    if duration is not None and (not isinstance(duration, int) or duration < 0):
        raise InvalidPayload("Invalid duration")
    popularity = item.get("popularity")
    if popularity is not None and (not isinstance(popularity, (int, float)) or not 0 <= popularity <= 100):
        raise InvalidPayload("Invalid popularity")
    return Track(
        title=title,
        artist=Artist(name=artist_name, provider_artist_id=nonempty(artists[0].get("id"))),
        album=Album(name=album_name, provider_album_id=nonempty(album.get("id"))) if album_name else None,
        duration_ms=duration,
        artwork_url=safe_https_url(album.get("picUrl")) or safe_https_url(album.get("blurPicUrl")),
        source=ProviderSource(provider="netease", provider_track_id=track_id,
                              external_url=f"https://music.163.com/#/song?id={track_id}"),
        popularity=popularity,
        canonical_key=canonical_key(title, artist_name),
    )


class NetEaseProvider(HTTPMusicProvider):
    name = "netease"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(provider=self.name, search_tracks=True, search_artist_tracks=True,
                                    stability="unverified", max_results=25)

    def _search(self, term: str, limit: int) -> list[Track]:
        term = self._bounded_query(term)
        payload: Mapping[str, object] = self._request(
            "POST", "https://music.163.com/api/search/get/web",
            data={"s": term, "type": "1", "offset": "0", "total": "true", "limit": str(limit)},
            headers={"Referer": "https://music.163.com/"},
        )
        result = optional_object(payload.get("result"))
        items = require_list(result.get("songs"))
        return [track for value in items[:limit] if (track := map_netease_track(value))]

    def search_tracks(self, query: str, limit: int) -> ProviderResult:
        return self._execute(lambda: self._search(query, self._bounded_limit(limit)))

    def lookup_track(self, identifier: str) -> ProviderResult:
        def fetch():
            if not identifier.isdecimal() or len(identifier) > 20:
                raise InvalidPayload("Invalid recording ID")
            payload = self._request("GET", "https://music.163.com/api/song/detail/",
                params={"id": identifier, "ids": json.dumps([int(identifier)])},
                headers={"Referer": "https://music.163.com/"})
            return [track for item in require_list(payload.get("songs"))[:25]
                    if (track := map_netease_track(item)) and track.source.provider_track_id == identifier]
        return self._execute(fetch)

    def search_artist_tracks(self, artist: str, limit: int) -> ProviderResult:
        return self._execute(lambda: [track for track in self._search(artist, self._bounded_limit(limit))
                                      if artist_matches(track, artist)])
