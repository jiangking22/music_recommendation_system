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
)


def map_qq_track(value: object) -> Track | None:
    item = optional_object(value)
    track_id = nonempty(item.get("id")) or nonempty(item.get("songid"))
    mid = nonempty(item.get("mid")) or nonempty(item.get("songmid"))
    title = nonempty(item.get("title")) or nonempty(item.get("songname"))
    people = item.get("singer", [])
    if not isinstance(people, list):
        raise InvalidPayload("Invalid singers")
    artists = [optional_object(person) for person in people]
    names = [name for person in artists if (name := nonempty(person.get("name")))]
    if not (track_id and title and names):
        return None
    artist_name = ", ".join(names)
    album = optional_object(item.get("album"))
    album_name = nonempty(album.get("name")) or nonempty(item.get("albumname"))
    album_mid = nonempty(album.get("mid")) or nonempty(item.get("albummid"))
    seconds = item.get("interval")
    if seconds is not None and (not isinstance(seconds, int) or seconds < 0):
        raise InvalidPayload("Invalid interval")
    return Track(
        title=title,
        artist=Artist(name=artist_name, provider_artist_id=nonempty(artists[0].get("id"))),
        album=Album(name=album_name, provider_album_id=nonempty(album.get("id"))) if album_name else None,
        duration_ms=seconds * 1000 if seconds is not None else None,
        artwork_url=f"https://y.gtimg.cn/music/photo_new/T002R300x300M000{album_mid}.jpg" if album_mid else None,
        source=ProviderSource(provider="qq", provider_track_id=track_id,
                              external_url=f"https://y.qq.com/n/ryqq/songDetail/{mid}" if mid else None),
        canonical_key=canonical_key(title, artist_name),
    )


class QQProvider(HTTPMusicProvider):
    name = "qq"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(provider=self.name, search_tracks=True, search_artist_tracks=True,
                                    stability="unverified", max_results=25)

    def _search(self, term: str, limit: int) -> list[Track]:
        term = self._bounded_query(term)
        payload: Mapping[str, object] = self._request(
            "GET", "https://c.y.qq.com/soso/fcgi-bin/client_search_cp",
            jsonp=True,
            params={"p": "1", "n": str(limit), "w": term, "format": "json"},
            headers={"Referer": "https://y.qq.com/"},
        )
        data = optional_object(payload.get("data"))
        song = optional_object(data.get("song"))
        items = require_list(song.get("list"))
        return [track for value in items[:limit] if (track := map_qq_track(value))]

    def search_tracks(self, query: str, limit: int) -> ProviderResult:
        return self._execute(lambda: self._search(query, self._bounded_limit(limit)))

    def search_artist_tracks(self, artist: str, limit: int) -> ProviderResult:
        return self._execute(lambda: [track for track in self._search(artist, self._bounded_limit(limit))
                                      if artist_matches(track, artist)])
