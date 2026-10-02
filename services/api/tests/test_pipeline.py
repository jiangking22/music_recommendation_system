from app.domain.music import Artist, ProviderSource, Track
from app.domain.pipeline import (
    dedup_key,
    deduplicate,
    extract_features,
    rank,
    rerank_diverse,
)
from app.domain.profile import PreferenceProfile


def track(title: str, artist: str, provider: str, *, genres=(), tags=(), popularity=50, language="en") -> Track:
    return Track(title=title, artist=Artist(name=artist),
                 source=ProviderSource(provider=provider, provider_track_id=f"{provider}-{title}"),
                 canonical_key=f"{title}::{artist}", genres=list(genres), tags=list(tags),
                 popularity=popularity, language=language)


def test_cross_provider_dedup_normalizes_versions_and_preserves_sources() -> None:
    songs = [track(" Café Song (feat. Guest)", "The  Artist", "itunes"),
             track("Cafe\u0301 Song - Remastered 2020", "the artist", "netease"),
             track("Other Song (Live)", "The Artist", "qq")]
    merged = deduplicate(songs)
    assert len(merged) == 2
    assert {source.provider for source in merged[0].provenance} == {"itunes", "netease"}


def test_common_version_suffixes_share_one_canonical_key() -> None:
    base = dedup_key(track("Song", "A", "itunes"))
    for title in ("Song feat. B", "Song (featuring B)", "Song - Live", "Song [Remaster]",
                  "Song - Remastered 2020", "Song (Explicit)"):
        assert dedup_key(track(title, "A", "netease")) == base


def test_features_scoring_explanation_and_determinism() -> None:
    songs = deduplicate([track("Blue Night", "A", "itunes", genres=("jazz",), tags=("night",), popularity=80),
                         track("Morning Sun", "B", "netease", genres=("pop",), popularity=90)])
    profile = PreferenceProfile(artist_affinity={"a": 1.0}, genre_affinity={"jazz": 1.0},
                                language_affinity={"en": 1.0}, disliked_tracks=set())
    features = extract_features(songs[0].track, "night", profile, songs[0].provenance)
    assert features["seed_relevance"] > 0
    first = rank(songs, "night", profile)
    assert first == rank(songs, "night", profile)
    assert first[0].track.title == "Blue Night"
    assert first[0].score == sum(first[0].score_breakdown.values())
    assert "jazz" in first[0].explanation.lower() or "artist" in first[0].explanation.lower()


def test_like_and_dislike_change_order() -> None:
    songs = deduplicate([track("One", "A", "itunes", genres=("jazz",)),
                         track("Two", "B", "netease", genres=("pop",))])
    liked = PreferenceProfile(artist_affinity={"b": 1.0}, genre_affinity={"pop": 1.0})
    disliked = PreferenceProfile(disliked_tracks={songs[1].key})
    assert rank(songs, "unknown", liked)[0].track.title == "Two"
    assert rank(songs, "unknown", disliked)[-1].track.title == "Two"


def test_negative_preference_is_explained() -> None:
    songs = deduplicate([track("One", "A", "itunes", genres=("jazz",))])
    profile = PreferenceProfile(artist_affinity={"a": -1.0})
    result = rank(songs, "unknown", profile)[0]
    assert result.score_breakdown["artist_affinity"] < 0
    assert "less aligned" in result.explanation


def test_diversity_avoids_adjacent_artist_provider_and_genre() -> None:
    songs = deduplicate([track(f"A{i}", "A", "itunes", genres=("jazz",), popularity=90-i) for i in range(3)]
                          + [track("B", "B", "netease", genres=("pop",), popularity=80)])
    ranked = rank(songs, "unknown", PreferenceProfile())
    diverse = rerank_diverse(ranked, 3)
    assert diverse[0].track.artist.name != diverse[1].track.artist.name
    assert len(diverse) == 3
