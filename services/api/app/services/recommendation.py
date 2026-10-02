from time import perf_counter

from app.domain.music import Artist, ProviderSource, SearchResult, Track, canonical_key
from app.domain.pipeline import RankedTrack, deduplicate, rank, rerank_diverse
from app.domain.profile import PreferenceProfile
from app.domain.recommendation import fixture_songs
from app.observability.events import emit
from app.providers.registry import ProviderRegistry


def local_catalog() -> list[Track]:
    return [Track(title=song.title, artist=Artist(name=song.artist),
                  source=ProviderSource(provider="fixture", provider_track_id=song.id),
                  canonical_key=canonical_key(song.title, song.artist), tags=list(song.tags))
            for song in fixture_songs()]


def recommend(seed: str, limit: int, registry: ProviderRegistry,
              profile: PreferenceProfile | None = None) -> tuple[list[RankedTrack], SearchResult]:
    started = perf_counter()
    # Request extra candidates before final truncation; the registry retains its 25/source cap.
    search = registry.search_tracks(seed, min(25, max(limit * 3, 10)))
    candidates = deduplicate(search.tracks + local_catalog())
    ranked = rank(candidates, seed, profile or PreferenceProfile())
    result = rerank_diverse(ranked, limit)
    emit("recommendation", candidate_count=len(candidates), result_count=len(result),
         source_count=len(search.sources), failed_sources=sum(bool(s.error) for s in search.sources.values()),
         personalized=profile is not None, latency_ms=round((perf_counter() - started) * 1000, 3))
    return result, search
