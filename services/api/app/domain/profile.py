from dataclasses import dataclass, field

from app.domain.music import normalize_text


@dataclass(frozen=True)
class FeedbackSignal:
    track_key: str
    value: str
    artist: str
    genres: tuple[str, ...]
    tags: tuple[str, ...]
    language: str | None


@dataclass(frozen=True)
class PreferenceProfile:
    artist_affinity: dict[str, float] = field(default_factory=dict)
    genre_affinity: dict[str, float] = field(default_factory=dict)
    tag_affinity: dict[str, float] = field(default_factory=dict)
    language_affinity: dict[str, float] = field(default_factory=dict)
    disliked_tracks: set[str] = field(default_factory=set)


def profile_from_feedback(signals: list[FeedbackSignal], decay: float = 0.98) -> PreferenceProfile:
    affinities: dict[str, dict[str, float]] = {name: {} for name in ("artist", "genre", "tag", "language")}
    disliked: set[str] = set()
    for index, signal in enumerate(signals):
        weight = (1.0 if signal.value == "like" else -1.0) * decay**index
        if signal.value == "dislike":
            disliked.add(signal.track_key)
        values = {
            "artist": (signal.artist,),
            "genre": signal.genres,
            "tag": signal.tags,
            "language": (signal.language,) if signal.language else (),
        }
        for kind, entries in values.items():
            for entry in {normalize_text(value) for value in entries if value}:
                affinities[kind][entry] = max(-1.0, min(1.0, affinities[kind].get(entry, 0.0) + weight))
    return PreferenceProfile(artist_affinity=affinities["artist"], genre_affinity=affinities["genre"],
                             tag_affinity=affinities["tag"], language_affinity=affinities["language"],
                             disliked_tracks=disliked)
