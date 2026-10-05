from dataclasses import dataclass
from time import perf_counter

from app.domain.discovery import (
    SeedStatus,
    is_alternate,
    original_hint,
    rank_related,
    resolve_seed,
)
from app.domain.music import (
    Artist,
    ProviderResult,
    ProviderSource,
    SearchResult,
    Track,
    canonical_key,
)
from app.domain.pipeline import RankedTrack, deduplicate, rank, rerank_diverse
from app.domain.profile import PreferenceProfile
from app.domain.recommendation import fixture_songs
from app.observability.events import emit
from app.providers.registry import ProviderRegistry

MAX_DISCOVERY_OPERATIONS = 3
MAX_DISCOVERY_SOURCES = 3


@dataclass(frozen=True)
class DiscoveryResult:
    items: list[RankedTrack]
    search: SearchResult
    seed_track: Track | None
    seed_candidates: list[Track]
    seed_status: SeedStatus


def local_catalog() -> list[Track]:
    return [Track(title=song.title, artist=Artist(name=song.artist),
                  source=ProviderSource(provider="fixture", provider_track_id=song.id),
                  canonical_key=canonical_key(song.title, song.artist), tags=list(song.tags))
            for song in fixture_songs()]


def _bounded_search(search: SearchResult, limit: int) -> SearchResult:
    sources = {name: result.model_copy(update={"tracks": result.tracks[:limit]})
               for name, result in list(search.sources.items())[:MAX_DISCOVERY_SOURCES]}
    counts: dict[str, int] = {}
    tracks = []
    for track in search.tracks[:limit * MAX_DISCOVERY_SOURCES]:
        provider = track.source.provider
        if counts.get(provider, 0) < limit:
            tracks.append(track)
            counts[provider] = counts.get(provider, 0) + 1
    return SearchResult(tracks=tracks, sources=sources)


def _merge_searches(searches: list[SearchResult]) -> SearchResult:
    tracks = []
    sources: dict[str, ProviderResult] = {}
    for search in searches:
        tracks.extend(search.tracks)
        for name, result in search.sources.items():
            previous = sources.get(name)
            sources[name] = ProviderResult(provider=name,
                tracks=(previous.tracks if previous else []) + result.tracks,
                error=(previous.error if previous else None) or result.error)
    return SearchResult(tracks=tracks, sources=sources)


def discover(seed: str, limit: int, registry: ProviderRegistry,
             profile: PreferenceProfile | None = None, seed_artist: str | None = None) -> DiscoveryResult:
    started = perf_counter()
    # Request extra candidates before final truncation; the registry retains its 25/source cap.
    recall_limit = min(25, max(limit * 3, 10))
    searches = [_bounded_search(registry.search_tracks(seed, recall_limit), recall_limit)]
    search = _merge_searches(searches)
    resolution = resolve_seed(seed, search.tracks, seed_artist)
    hint = original_hint(seed, seed_artist)
    if resolution.status == "unresolved" and (hint or seed_artist):
        title = hint[0] if hint else seed
        artist = seed_artist or hint[1][0]
        query = f"{title} {artist}"[:120]
        if query != seed:
            searches.append(_bounded_search(registry.search_tracks(query, recall_limit), recall_limit))
            search = _merge_searches(searches)
            resolution = resolve_seed(seed, search.tracks, seed_artist)

    if resolution.track is not None:
        searches.append(_bounded_search(
            registry.search_tracks(resolution.track.artist.name[:120], recall_limit), recall_limit))
        features = [*resolution.track.genres[:1], *resolution.track.tags[:1]]
        related_query = " ".join(value.strip() for value in features if value.strip())[:120]
        if related_query and len(searches) < MAX_DISCOVERY_OPERATIONS:
            searches.append(_bounded_search(registry.search_tracks(related_query, recall_limit), recall_limit))
        search = _merge_searches(searches)
        candidates = deduplicate([track for track in search.tracks if not is_alternate(track)])
        ranked = rank_related(candidates, resolution.track, profile or PreferenceProfile())
    elif resolution.status == "ambiguous" or hint or seed_artist or resolution.title_matches:
        candidates, ranked = [], []
    else:
        # Theme/genre prompts retain the existing offline catalog and deterministic policy.
        candidates = deduplicate(search.tracks + local_catalog())
        ranked = rank(candidates, seed, profile or PreferenceProfile())
    items = rerank_diverse(ranked, limit)
    emit("recommendation", candidate_count=len(candidates), result_count=len(items),
         source_count=len(search.sources), failed_sources=sum(bool(s.error) for s in search.sources.values()),
         personalized=profile is not None, latency_ms=round((perf_counter() - started) * 1000, 3))
    return DiscoveryResult(items, search, resolution.track, resolution.candidates, resolution.status)


def recommend(seed: str, limit: int, registry: ProviderRegistry,
              profile: PreferenceProfile | None = None) -> tuple[list[RankedTrack], SearchResult]:
    result = discover(seed, limit, registry, profile)
    return result.items, result.search
