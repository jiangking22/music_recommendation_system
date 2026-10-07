"""Unknown catalog properties can be enriched without overriding recording evidence."""

import pytest

from app.domain import listening
from app.domain.music import Artist, ProviderSource, Track, canonical_key


def track(title="Quiet Song", *, tags=(), language=None):
    return Track(
        title=title,
        artist=Artist(name="Catalog Artist"),
        source=ProviderSource(provider="itunes", provider_track_id=title),
        canonical_key=canonical_key(title, "Catalog Artist"),
        tags=list(tags),
        language=language,
    )


def evidence(song, attribute, value, *, origin="model", track_id=None):
    return listening.AttributeEvidence(
        attribute=attribute,
        value=value,
        origin=origin,
        source_url="https://music.apple.com/recording/quiet-song" if origin != "model" else None,
        basis="Property supplied for this exact catalog recording.",
        track_id=track_id or song.canonical_key,
    )


@pytest.mark.parametrize("constraints", [
    listening.ListeningConstraints(vocals="vocal"),
    listening.ListeningConstraints(vocals="instrumental"),
    listening.ListeningConstraints(language="zh"),
])
def test_missing_catalog_property_is_unknown_rather_than_mismatch(constraints):
    song = track("中文歌名 alone does not establish language or vocals")

    assert constraints.assess(song) == "unknown"
    assert constraints.matches(song) is False


@pytest.mark.parametrize(("constraints", "song"), [
    (listening.ListeningConstraints(vocals="vocal"), track(tags=("vocal",))),
    (listening.ListeningConstraints(vocals="instrumental"), track(tags=("纯音乐",))),
    (listening.ListeningConstraints(language="zh"), track(language="Mandarin")),
    (listening.ListeningConstraints(language="en"), track(tags=("English",))),
])
def test_matching_catalog_metadata_satisfies_constraint(constraints, song):
    assert constraints.assess(song) == "match"
    assert constraints.matches(song) is True


def test_model_vocal_inference_can_fill_missing_catalog_metadata():
    song = track()
    constraints = listening.ListeningConstraints(vocals="vocal")
    inferred = [evidence(song, "vocals", "vocal")]

    assert constraints.assess(song, inferred) == "match"
    assert constraints.matches(song, inferred) is True
    assert song.tags == []  # Inference is not promoted into provider metadata.


def test_model_must_supply_each_requested_unknown_property():
    song = track()
    constraints = listening.ListeningConstraints(language="zh", vocals="vocal")

    assert constraints.assess(song, [evidence(song, "vocals", "vocal")]) == "unknown"
    assert constraints.assess(song, [
        evidence(song, "vocals", "vocal"), evidence(song, "language", "zh"),
    ]) == "match"


@pytest.mark.parametrize(("constraints", "song", "attribute", "value"), [
    (listening.ListeningConstraints(vocals="vocal"), track(tags=("instrumental",)),
     "vocals", "vocal"),
    (listening.ListeningConstraints(language="zh"), track(language="en"),
     "language", "zh"),
])
def test_model_inference_cannot_override_explicit_catalog_mismatch(
    constraints, song, attribute, value,
):
    inferred = [evidence(song, attribute, value)]

    assert constraints.assess(song, inferred) == "mismatch"
    assert constraints.matches(song, inferred) is False


def test_model_mismatch_cannot_override_matching_provider_metadata():
    song = track(tags=("vocal",))
    constraints = listening.ListeningConstraints(vocals="vocal")

    assert constraints.assess(song, [evidence(song, "vocals", "instrumental")]) == "match"


@pytest.mark.parametrize("origin", ["provider", "web"])
def test_sourced_recording_property_takes_precedence_over_model_guess(origin):
    song = track()
    constraints = listening.ListeningConstraints(vocals="vocal")
    properties = [
        evidence(song, "vocals", "vocal"),
        evidence(song, "vocals", "instrumental", origin=origin),
    ]

    assert constraints.assess(song, properties) == "mismatch"
    assert constraints.matches(song, properties) is False


@pytest.mark.parametrize("origin", ["provider", "web", "model"])
def test_evidence_for_another_recording_version_cannot_fill_unknown_property(origin):
    song = track("Quiet Song (Instrumental Version)")
    other_recording = track("Quiet Song (Original Version)")
    constraints = listening.ListeningConstraints(vocals="vocal")
    wrong_version = [evidence(song, "vocals", "vocal", origin=origin,
                              track_id=other_recording.canonical_key)]

    assert constraints.assess(song, wrong_version) == "unknown"
    assert constraints.matches(song, wrong_version) is False


def test_model_uncertainty_remains_unknown():
    song = track()
    constraints = listening.ListeningConstraints(vocals="vocal")

    assert constraints.assess(song, [evidence(song, "vocals", None)]) == "unknown"
    assert constraints.matches(song, [evidence(song, "vocals", None)]) is False


def test_conflicting_sourced_evidence_does_not_count_as_a_match():
    song = track()
    constraints = listening.ListeningConstraints(vocals="vocal")
    properties = [
        evidence(song, "vocals", "vocal", origin="provider"),
        evidence(song, "vocals", "instrumental", origin="web"),
    ]

    assert constraints.assess(song, properties) != "match"
    assert constraints.matches(song, properties) is False


def test_no_constraints_match_without_any_attribute_evidence():
    song = track()
    constraints = listening.ListeningConstraints()

    assert constraints.assess(song) == "match"
    assert constraints.matches(song) is True


def test_sadness_does_not_negate_or_prove_a_calm_listening_feel():
    song=track(tags=('sad',))
    constraints=listening.ListeningConstraints(feel='calm')
    assert constraints.assess(song)=='unknown'
    assert constraints.assess(song,[evidence(song,'feel','calm')])=='match'
    song.tags.append('calm')
    assert constraints.assess(song)=='match'
