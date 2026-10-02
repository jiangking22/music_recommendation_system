import re
import unicodedata
from dataclasses import dataclass

from app.domain.music import ProviderSource, Track, normalize_text
from app.domain.policy import POLICY, RecommendationPolicy
from app.domain.profile import PreferenceProfile

_VERSION = re.compile(
    r"(?:\s*[\[(]\s*|\s*[-–—]\s*)(?:feat\.?|featuring|ft\.?|live|remaster(?:ed)?(?:\s+\d{4})?|explicit)\b.*$",
    re.IGNORECASE,
)
_FEATURED = re.compile(r"\s+(?:feat\.?|featuring|ft\.?)\s+.*$", re.IGNORECASE)


def dedup_key(track: Track) -> str:
    title = _FEATURED.sub("", _VERSION.sub("", unicodedata.normalize("NFKC", track.title))).strip()
    artist = _FEATURED.sub("", _VERSION.sub("", unicodedata.normalize("NFKC", track.artist.name))).strip()
    return f"{normalize_text(title)}::{normalize_text(artist)}"


@dataclass(frozen=True)
class Candidate:
    key: str
    track: Track
    provenance: tuple[ProviderSource, ...]


@dataclass(frozen=True)
class RankedTrack:
    key: str
    track: Track
    provenance: tuple[ProviderSource, ...]
    score: float
    score_breakdown: dict[str, float]
    explanation: str


def deduplicate(tracks: list[Track]) -> list[Candidate]:
    merged: dict[str, Candidate] = {}
    for track in tracks:
        key = dedup_key(track)
        previous = merged.get(key)
        if previous is None:
            merged[key] = Candidate(key, track, (track.source,))
            continue
        sources = {f"{source.provider}:{source.provider_track_id}": source for source in previous.provenance}
        sources[f"{track.source.provider}:{track.source.provider_track_id}"] = track.source
        # The richer metadata wins; ties keep the first provider's canonical representation.
        richness = lambda item: len(item.genres) + len(item.tags) + int(item.popularity is not None)
        representative = track if richness(track) > richness(previous.track) else previous.track
        merged[key] = Candidate(key, representative, tuple(sources.values()))
    return list(merged.values())


def extract_features(track: Track, seed: str, profile: PreferenceProfile,
                     provenance: tuple[ProviderSource, ...],
                     policy: RecommendationPolicy = POLICY) -> dict[str, float]:
    query = normalize_text(seed)
    title = normalize_text(track.title)
    artist = normalize_text(track.artist.name)
    tags = {normalize_text(tag) for tag in track.tags}
    genres = {normalize_text(genre) for genre in track.genres}
    seed_tokens = set(query.split())
    catalog_tokens = set((title + " " + artist).split()) | tags | genres
    relevance = len(seed_tokens & catalog_tokens) / len(seed_tokens) if seed_tokens else 0.0
    return {
        "seed_relevance": relevance,
        "artist_affinity": profile.artist_affinity.get(artist, 0.0),
        "genre_affinity": max((profile.genre_affinity.get(genre, 0.0) for genre in genres), default=0.0),
        "tag_affinity": max((profile.tag_affinity.get(tag, 0.0) for tag in tags), default=0.0),
        "language_affinity": profile.language_affinity.get(normalize_text(track.language or ""), 0.0),
        "popularity": (track.popularity or 0.0) / 100.0,
        "source_confidence": max((policy.documented_source_confidence if source.provider == "itunes"
                                  else policy.local_source_confidence if source.provider == "fixture"
                                  else policy.unverified_source_confidence for source in provenance), default=0.0),
        "disliked_track": 1.0 if dedup_key(track) in profile.disliked_tracks else 0.0,
    }


def explain(features: dict[str, float]) -> str:
    reasons = []
    if features["seed_relevance"] > 0:
        reasons.append("matches your seed")
    if features["artist_affinity"] > 0:
        reasons.append("matches a liked artist")
    if features["genre_affinity"] > 0:
        reasons.append("matches a preferred genre")
    if features["tag_affinity"] > 0:
        reasons.append("matches a preferred tag")
    if features["language_affinity"] > 0:
        reasons.append("matches a preferred language")
    if features["disliked_track"] > 0:
        reasons.append("previously disliked")
    if any(features[name] < 0 for name in ("artist_affinity", "genre_affinity",
                                            "tag_affinity", "language_affinity")):
        reasons.append("less aligned with past feedback")
    return "; ".join(reasons) if reasons else "Available from the catalog."


def rank(candidates: list[Candidate], seed: str, profile: PreferenceProfile,
         policy: RecommendationPolicy = POLICY) -> list[RankedTrack]:
    output = []
    for candidate in candidates:
        features = extract_features(candidate.track, seed, profile, candidate.provenance, policy)
        breakdown = {name: round(value * getattr(policy, name), 6) if value else 0.0
                     for name, value in features.items()}
        output.append(RankedTrack(candidate.key, candidate.track, candidate.provenance,
                                  round(sum(breakdown.values()), 6), breakdown, explain(features)))
    return sorted(output, key=lambda item: (-item.score, item.key))


def rerank_diverse(ranked: list[RankedTrack], limit: int,
                   policy: RecommendationPolicy = POLICY) -> list[RankedTrack]:
    selected: list[RankedTrack] = []
    remaining = ranked.copy()
    while remaining and len(selected) < limit:
        def adjusted(item: RankedTrack) -> tuple[float, float, str]:
            artist = normalize_text(item.track.artist.name)
            providers = {source.provider for source in item.provenance}
            genres = {normalize_text(genre) for genre in item.track.genres}
            penalty = sum(
                policy.diversity_artist * (artist == normalize_text(chosen.track.artist.name))
                + policy.diversity_provider * bool(providers & {source.provider for source in chosen.provenance})
                + policy.diversity_genre * bool(genres & {normalize_text(g) for g in chosen.track.genres})
                for chosen in selected
            )
            return (item.score - penalty, item.score, item.key)
        best = min(remaining, key=lambda item: (-adjusted(item)[0], -adjusted(item)[1], adjusted(item)[2]))
        selected.append(best)
        remaining.remove(best)
    return selected
