from dataclasses import dataclass, field, replace
from time import perf_counter

from app.domain.artist_names import artist_identity, enrich_track
from app.domain.discovery import (
    SeedResolution,
    SeedStatus,
    is_alternate,
    original_hint,
    rank_related,
    recording_title,
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
from app.domain.pipeline import (
    Candidate,
    RankedTrack,
    deduplicate,
    rank,
    rerank_diverse,
)
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


@dataclass
class DiscoverySearch:
    """Request-local search budget shared by identification and deterministic recall."""

    seed: str
    limit: int
    registry: ProviderRegistry
    profile: PreferenceProfile
    seed_artist: str | None
    resolution: SeedResolution
    searches: list[SearchResult] = field(default_factory=list)
    started: float = field(default_factory=perf_counter)
    personalized: bool = False

    @property
    def search(self) -> SearchResult:
        return _merge_searches(self.searches)

    def query(self, query: str) -> None:
        if len(self.searches) < MAX_DISCOVERY_OPERATIONS:
            recall_limit = min(25, max(self.limit * 3, 10))
            self.searches.append(_bounded_search(
                self.registry.search_tracks(query[:120], recall_limit), recall_limit))


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


def begin_discovery(seed: str, limit: int, registry: ProviderRegistry,
                    profile: PreferenceProfile | None = None,
                    seed_artist: str | None = None) -> DiscoverySearch:
    state = DiscoverySearch(seed, limit, registry, profile or PreferenceProfile(), seed_artist,
                            SeedResolution(None, [], "unresolved"), personalized=profile is not None)
    state.query(seed)
    state.resolution = resolve_seed(seed, state.search.tracks, seed_artist)
    hint = original_hint(seed, seed_artist)
    if state.resolution.status == "unresolved" and (hint or seed_artist):
        title = hint[0] if hint else seed
        artist = seed_artist or hint[1][0]
        query = f"{title} {artist}"[:120]
        if query != seed:
            state.query(query)
            state.resolution = resolve_seed(seed, state.search.tracks, seed_artist)
    return state


def match_model_seed(state: DiscoverySearch, title: str, artist: str) -> SeedResolution:
    def match() -> SeedResolution:
        result = resolve_seed(state.seed, state.search.tracks, artist)
        if result.track and recording_title(result.track.title) == recording_title(title):
            return result
        return SeedResolution(None, [], "unresolved", result.title_matches)

    resolution = match()
    if resolution.track is None:
        state.query(f"{title} {artist}")
        resolution = match()
    return resolution


def _recording_candidates(tracks: list[Track]) -> list[Candidate]:
    # Merge reviewed artist aliases locally while preserving the representative's existing key.
    merged: dict[tuple[str, str], Candidate] = {}
    for candidate in deduplicate([track for track in tracks if not is_alternate(track)]):
        identity = (candidate.key.split("::")[0], artist_identity(candidate.track.artist.name))
        previous = merged.get(identity)
        if previous is None:
            merged[identity] = candidate
        else:
            provenance = {(s.provider, s.provider_track_id): s
                          for s in (*previous.provenance, *candidate.provenance)}
            first, other = previous.track, candidate.track
            track = first.model_copy(update={
                "genres": list(dict.fromkeys([*first.genres, *other.genres])),
                "tags": list(dict.fromkeys([*first.tags, *other.tags])),
                "album": first.album or other.album,
                "language": first.language or other.language,
                "popularity": first.popularity if first.popularity is not None else other.popularity,
                "duration_ms": first.duration_ms if first.duration_ms is not None else other.duration_ms,
                "artwork_url": first.artwork_url or other.artwork_url,
            })
            merged[identity] = Candidate(previous.key, track, tuple(provenance.values()))
    return list(merged.values())


def finish_discovery(state: DiscoverySearch, resolution: SeedResolution | None = None,
                     *, allow_theme: bool = False) -> DiscoveryResult:
    resolution = resolution or state.resolution

    if resolution.track is not None:
        state.query(resolution.track.artist.name)
        features = [*resolution.track.genres[:1], *resolution.track.tags[:1]]
        related_query = " ".join(value.strip() for value in features if value.strip())[:120]
        if related_query:
            state.query(related_query)
        search = state.search
        candidates = _recording_candidates(search.tracks)
        ranked = rank_related(candidates, resolution.track, state.profile)
    elif allow_theme:
        # Theme/genre prompts retain the existing offline catalog and deterministic policy.
        search = state.search
        candidates = deduplicate(search.tracks + local_catalog())
        ranked = rank(candidates, state.seed, state.profile)
    else:
        search = state.search
        candidates, ranked = [], []
    items = [replace(item, track=enrich_track(item.track)) for item in rerank_diverse(ranked, state.limit)]
    emit("recommendation", candidate_count=len(candidates), result_count=len(items),
         source_count=len(search.sources), failed_sources=sum(bool(s.error) for s in search.sources.values()),
         personalized=state.personalized,
         latency_ms=round((perf_counter() - state.started) * 1000, 3))
    return DiscoveryResult(items, search, resolution.track, resolution.candidates, resolution.status)


def discover(seed: str, limit: int, registry: ProviderRegistry,
             profile: PreferenceProfile | None = None, seed_artist: str | None = None) -> DiscoveryResult:
    state = begin_discovery(seed, limit, registry, profile, seed_artist)
    resolution = state.resolution
    theme = not (resolution.title_matches or original_hint(seed, seed_artist) or seed_artist)
    return finish_discovery(state, allow_theme=theme)


def recommend(seed: str, limit: int, registry: ProviderRegistry,
              profile: PreferenceProfile | None = None) -> tuple[list[RankedTrack], SearchResult]:
    result = discover(seed, limit, registry, profile)
    return result.items, result.search
