from app.domain.music import Artist, ProviderSource, SearchResult, Track, canonical_key
from app.domain.pipeline import RankedTrack, deduplicate, rank, rerank_diverse
from app.domain.profile import PreferenceProfile
from app.domain.recommendation import fixture_songs
from app.providers.registry import ProviderRegistry


def local_catalog() -> list[Track]:
    return [Track(title=song.title, artist=Artist(name=song.artist),
                  source=ProviderSource(provider="fixture", provider_track_id=song.id),
                  canonical_key=canonical_key(song.title, song.artist), tags=list(song.tags))
            for song in fixture_songs()]


def recommend(seed: str, limit: int, registry: ProviderRegistry,
              profile: PreferenceProfile | None = None) -> tuple[list[RankedTrack], SearchResult]:
    # Request extra candidates before final truncation; the registry retains its 25/source cap.
    search = registry.search_tracks(seed, min(25, max(limit * 3, 10)))
    candidates = deduplicate(search.tracks + local_catalog())
    ranked = rank(candidates, seed, profile or PreferenceProfile())
    return rerank_diverse(ranked, limit), search
