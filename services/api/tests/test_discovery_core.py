from app.domain.discovery import is_alternate, recording_title
from app.domain.music import (
    Album,
    Artist,
    ProviderError,
    ProviderResult,
    ProviderSource,
    SearchResult,
    Track,
    canonical_key,
)
from app.domain.pipeline import deduplicate, rank, rerank_diverse
from app.domain.profile import PreferenceProfile
from app.services.recommendation import discover, local_catalog, recommend


def song(title, artist, *, genres=(), tags=(), popularity=50, language="zh", provider="itunes"):
    return Track(title=title, artist=Artist(name=artist),
                 source=ProviderSource(provider=provider, provider_track_id=f"{title}-{artist}"),
                 canonical_key=canonical_key(title, artist), genres=list(genres), tags=list(tags),
                 popularity=popularity, language=language)


def result(tracks=(), error=None):
    return SearchResult(tracks=list(tracks), sources={"itunes": ProviderResult(
        provider="itunes", tracks=list(tracks), error=error)})


class CatalogRegistry:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def search_tracks(self, query, limit):
        self.calls.append((query, limit))
        return self.responses.get(query, result())


def test_known_original_beats_more_popular_cover_and_recalls_related_songs():
    original = song("我好想你", "蘇打綠", genres=("Mandopop",), popularity=10)
    cover = song("我好想你", "Cover Singer", genres=("Mandopop",), popularity=100)
    related = song("小情歌", "苏打绿", genres=("Mandopop",))
    registry = CatalogRegistry({"我好想你": result([cover, original]),
                                "蘇打綠": result([original, related])})
    discovery = discover("我好想你", 5, registry)
    assert discovery.seed_status == "matched"
    assert discovery.seed_track == original
    assert [item.track.title for item in discovery.items] == ["小情歌"]
    assert discovery.items[0].score_breakdown["seed_artist"] > 0
    assert "same artist" in discovery.items[0].explanation
    assert len(registry.calls) <= 3


def test_original_missing_from_initial_page_triggers_bounded_qualified_search():
    original = song("我好想你", "sodagreen", genres=("Mandopop",))
    related = song("無與倫比的美麗", "sodagreen", genres=("Mandopop",))
    registry = CatalogRegistry({"我好想你": result([song("我好想你", "Cover Singer")]),
                                "我好想你 苏打绿": result([original]),
                                "sodagreen": result([related])})
    discovery = discover("我好想你", 25, registry)
    assert discovery.seed_track == original
    assert [item.track.title for item in discovery.items] == [related.title]
    assert len(registry.calls) == 3
    assert all(1 <= limit <= 25 and len(query) <= 120 for query, limit in registry.calls)


def test_missing_verified_original_does_not_present_cover_or_demo_as_related():
    registry = CatalogRegistry({"我好想你": result([song("我好想你", "Cover Singer")])})
    discovery = discover("我好想你", 5, registry)
    assert discovery.seed_status == "unresolved"
    assert discovery.seed_track is None
    assert discovery.items == []


def test_unknown_multi_artist_title_requires_confirmation_even_when_one_is_popular():
    registry = CatalogRegistry({"Shared Title": result([
        song("Shared Title", "First", popularity=99),
        song("Shared Title", "Second", popularity=1),
    ])})
    discovery = discover("Shared Title", 5, registry)
    assert discovery.seed_status == "ambiguous"
    assert discovery.seed_track is None
    assert {track.artist.name for track in discovery.seed_candidates} == {"First", "Second"}
    assert discovery.items == []
    assert len(registry.calls) == 1


def test_confirmed_artist_resolves_ambiguity_and_excludes_all_seed_versions():
    first = song("Shared Title", "First")
    second = song("Shared Title", "Second", genres=("pop",))
    related = song("Next Song", "Second", genres=("pop",))
    registry = CatalogRegistry({"Shared Title": result([first, second]), "Second": result([
        related, song("Shared Title (Live)", "Second"),
        song("Shared Title (Cover First)", "Cover Singer"),
        song("Shared Title - Karaoke", "Karaoke Band"),
    ])})
    discovery = discover("Shared Title", 5, registry, seed_artist="Second")
    assert discovery.seed_track == second
    assert [item.track.title for item in discovery.items] == ["Next Song"]


def test_original_title_aliases_are_excluded_from_related_results():
    original = song("我好想你 (苏打绿版)", "苏打绿", genres=("Mandopop",))
    related = song("小情歌", "苏打绿", genres=("Mandopop",))
    registry = CatalogRegistry({"我好想你": result([original]), "苏打绿": result([
        related, song("I Miss You So (sodagreen Version)", "sodagreen", genres=("Mandopop",)),
        song("I Miss You So", "Dianao Zhou", genres=("Mandopop",)),
    ])})
    discovery = discover("我好想你", 5, registry)
    assert discovery.seed_track == original
    assert [item.track.title for item in discovery.items] == ["小情歌"]


def test_unqualified_translated_title_remains_a_valid_other_artist_song():
    seed = song("I Miss You So", "Nat King Cole", genres=("jazz",))
    related = song("Another Jazz Song", "Nat King Cole", genres=("jazz",))
    registry = CatalogRegistry({"I Miss You So": result([seed]), "Nat King Cole": result([related])})
    discovery = discover("I Miss You So", 5, registry)
    assert discovery.seed_track == seed
    assert discovery.seed_status == "matched"
    assert [item.track for item in discovery.items] == [related]


def test_unqualified_translated_title_exposes_multi_artist_ambiguity():
    candidates = [song("I Miss You So", "Nat King Cole"), song("I Miss You So", "sodagreen")]
    registry = CatalogRegistry({"I Miss You So": result(candidates)})
    discovery = discover("I Miss You So", 5, registry)
    assert discovery.seed_status == "ambiguous"
    assert discovery.seed_track is None
    assert discovery.seed_candidates == candidates
    assert discovery.items == []


def test_artist_qualified_translated_title_can_resolve_the_verified_chinese_recording():
    original = song("我好想你", "蘇打綠")
    related = song("小情歌", "蘇打綠")
    registry = CatalogRegistry({"I Miss You So by sodagreen": result([original]),
                                "蘇打綠": result([related])})
    discovery = discover("I Miss You So by sodagreen", 5, registry)
    assert discovery.seed_track == original
    assert [item.track for item in discovery.items] == [related]


def test_richer_live_metadata_never_hides_available_studio_recording():
    studio = song("Reference", "Original", genres=("folk",))
    related = song("Neighbour", "Original", genres=("folk",))
    registry = CatalogRegistry({"Reference": result([
        studio, song("Reference (Live)", "Original", genres=("folk",), tags=("live", "acoustic")),
    ]), "Original": result([
        related, song("Neighbour (Live)", "Original", genres=("folk",), tags=("live", "acoustic")),
    ])})
    discovery = discover("Reference", 5, registry)
    assert discovery.seed_track == studio
    assert [item.track for item in discovery.items] == [related]


def test_artist_qualified_input_resolves_original_without_changing_track_metadata():
    original = song("我好想你", "蘇打綠")
    related = song("小情歌", "蘇打綠")
    registry = CatalogRegistry({"我好想你 苏打绿": result([original]),
                                "蘇打綠": result([related])})
    discovery = discover("我好想你 苏打绿", 5, registry)
    assert discovery.seed_track == original
    assert discovery.seed_track.artist.name == "蘇打綠"
    assert discovery.seed_status == "matched"


def test_by_artist_query_resolves_a_song_in_the_existing_homepage_prompt_format():
    original = song("Dreams", "Fleetwood Mac", genres=("rock",))
    related = song("Rhiannon", "Fleetwood Mac", genres=("rock",))
    registry = CatalogRegistry({"Dreams by Fleetwood Mac": result([original]),
                                "Fleetwood Mac": result([related])})
    discovery = discover("Dreams by Fleetwood Mac", 5, registry)
    assert discovery.seed_status == "matched"
    assert discovery.seed_track == original
    assert [item.track.title for item in discovery.items] == ["Rhiannon"]


def test_chinese_voice_and_instrument_versions_are_excluded_from_related_results():
    original = song("我好想你", "苏打绿", genres=("Mandopop",))
    related = song("小情歌", "苏打绿", genres=("Mandopop",))
    registry = CatalogRegistry({"我好想你": result([original]), "苏打绿": result([
        related, song("我好想你（女声版）", "Singer", genres=("Mandopop",)),
        song("我好想你女声版", "Singer", genres=("Mandopop",)),
        song("我好想你 - 原唱钢琴版", "Piano Player", genres=("Mandopop",)),
    ])})
    assert [item.track.title for item in discover("我好想你", 5, registry).items] == ["小情歌"]


def test_marked_cover_and_live_recordings_do_not_resolve_the_original():
    registry = CatalogRegistry({"Song": result([
        song("Song (Cover Original)", "Singer"),
        song("Song - Live", "Original"),
        song("Song (伴奏)", "Band"),
    ])})
    discovery = discover("Song", 5, registry)
    assert discovery.seed_track is None
    assert discovery.seed_status == "unresolved"
    assert discovery.items == []


def test_real_studio_titles_and_albums_with_version_words_remain_recommendable():
    for title, artist in (("Live Forever", "Oasis"), ("Live and Let Die", "Wings"),
                          ("Cover Me", "Bruce Springsteen"), ("Run For Cover", "The Killers"),
                          ("Tribute", "Tenacious D"), ("钢琴", "Singer")):
        studio = song(title, artist, genres=("rock",))
        studio.album = Album(name=title)
        related = song("Another Studio Song", artist, genres=("rock",))
        registry = CatalogRegistry({title: result([studio]), artist: result([related])})
        discovery = discover(title, 5, registry)
        assert not is_alternate(studio)
        assert recording_title(title)
        assert discovery.seed_track == studio
        assert [item.track for item in discovery.items] == [related]
        assert is_alternate(song(f"{title} (Live)", artist))


def test_related_recall_uses_seed_features_and_ignores_unrelated_popular_catalog():
    seed = song("Reference", "Original", genres=("folk",), tags=("acoustic",))
    related = song("Neighbour", "Another Artist", genres=("folk",), tags=("acoustic",), popularity=1)
    unrelated = song("Unrelated", "Pop Star", genres=("dance",), popularity=100)
    registry = CatalogRegistry({"Reference": result([seed]), "Original": result([unrelated]),
                                "folk acoustic": result([related, unrelated])})
    discovery = discover("Reference", 5, registry)
    assert [item.track.title for item in discovery.items] == ["Neighbour"]
    item = discovery.items[0]
    assert item.score_breakdown["seed_genre"] > 0
    assert item.score_breakdown["seed_tag"] > 0
    assert item.score == round(sum(item.score_breakdown.values()), 6)
    assert "genre" in item.explanation


def test_followup_failure_remains_visible_after_a_later_success():
    seed = song("Reference", "Original", genres=("folk",))
    related = song("Neighbour", "Another Artist", genres=("folk",))
    registry = CatalogRegistry({"Reference": result([seed]),
                                "Original": result(error=ProviderError(code="timeout", message="Unavailable")),
                                "folk": result([related])})
    discovery = discover("Reference", 5, registry)
    assert [item.track.title for item in discovery.items] == ["Neighbour"]
    assert discovery.search.sources["itunes"].error.code == "timeout"
    assert related in discovery.search.sources["itunes"].tracks


def test_unresolved_generic_theme_preserves_existing_deterministic_profile_ranking():
    profile = PreferenceProfile(tag_affinity={"night": 1.0})
    expected = rerank_diverse(rank(deduplicate(local_catalog()), "calm jazz", profile), 3)
    registry = CatalogRegistry({})
    discovery = discover("calm jazz", 3, registry, profile)
    assert discovery.seed_status == "unresolved"
    assert discovery.items == expected
    assert recommend("calm jazz", 3, CatalogRegistry({}), profile)[0] == expected


def test_ambiguity_candidates_are_bounded_without_assuming_first_five_are_unique():
    tracks = [song("Shared Title", f"Artist {i}") for i in range(30)]
    discovery = discover("Shared Title", 5, CatalogRegistry({"Shared Title": result(tracks)}))
    assert discovery.seed_status == "ambiguous"
    assert len(discovery.seed_candidates) == 5
    assert len(discovery.search.tracks) <= 25
