from dataclasses import dataclass, field


@dataclass(frozen=True)
class PreferenceProfile:
    artist_affinity: dict[str, float] = field(default_factory=dict)
    genre_affinity: dict[str, float] = field(default_factory=dict)
    tag_affinity: dict[str, float] = field(default_factory=dict)
    language_affinity: dict[str, float] = field(default_factory=dict)
    disliked_tracks: set[str] = field(default_factory=set)
