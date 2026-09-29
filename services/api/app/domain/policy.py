from dataclasses import dataclass


@dataclass(frozen=True)
class RecommendationPolicy:
    seed_relevance: float = 3.0
    artist_affinity: float = 2.0
    genre_affinity: float = 1.5
    tag_affinity: float = 1.0
    language_affinity: float = 0.8
    popularity: float = 0.3
    source_confidence: float = 0.4
    disliked_track: float = -8.0
    diversity_artist: float = 1.0
    diversity_provider: float = 0.4
    diversity_genre: float = 0.5
    documented_source_confidence: float = 1.0
    unverified_source_confidence: float = 0.6
    local_source_confidence: float = 0.4


POLICY = RecommendationPolicy()
