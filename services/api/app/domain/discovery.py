"""Deterministic recording resolution and related-song scoring over canonical tracks."""

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

from app.domain.artist_names import artist_aliases, artist_identity
from app.domain.music import Track, normalize_text
from app.domain.pipeline import Candidate, RankedTrack, deduplicate, rank
from app.domain.profile import PreferenceProfile

SeedStatus = Literal["matched", "ambiguous", "unresolved"]
SEED_WEIGHTS = {"seed_artist": 3.0, "seed_genre": 1.5, "seed_tag": 1.0, "seed_language": 0.4}

# These are small evidence-backed disambiguation hints, never recommendation lists.
# Official MV: https://www.youtube.com/watch?v=Zs8TRQ4PTYk
# Original recording: https://music.apple.com/us/song/1480717221
# 匆匆那年: https://music.apple.com/cn/album/966805714 (2014 Faye Productions Ltd.)
ORIGINAL_HINTS = {"我好想你": artist_aliases("苏打绿"), "匆匆那年": artist_aliases("王菲")}
TITLE_ALIASES = {"我好想你": ("我好想你", "I Miss You So")}

_ALTERNATE = re.compile(
    r"(?<![a-z])(?:cover(?:ed)?|karaoke|instrumental|live|remix|tribute)(?![a-z])"
    r"|翻唱|伴奏|现场|現場|純音樂|纯音乐|演唱会|演唱會", re.IGNORECASE,
)
_VERSION = re.compile(
    r"(?:\s*[\[(]\s*|\s*[-–—]\s*)(?:cover|karaoke|instrumental|live|remix|tribute|"
    r"feat\.?|featuring|ft\.?|remaster(?:ed)?|explicit|翻唱|伴奏|现场|現場|纯音乐|純音樂)(?![a-z]).*$",
    re.IGNORECASE,
)
_FEATURED = re.compile(r"\s+(?:feat\.?|featuring|ft\.?)(?![a-z]).*$", re.IGNORECASE)
_NAMED_VERSION = re.compile(r"\s*[\[(][^\])]*(?:版|version|edition)[)\]]\s*$", re.IGNORECASE)
_VOICE_VERSION = re.compile(
    r"\s*(?:[-–—]\s*)?(?:男声|女声|男聲|女聲|原唱(?:钢琴|鋼琴)?|钢琴|鋼琴)版\s*$",
)
_EXPLICIT_TAGS = {"live", "live recording", "live version", "cover", "karaoke", "instrumental",
                  "remix", "tribute", "翻唱", "伴奏", "现场", "現場", "纯音乐", "純音樂"}


@dataclass(frozen=True)
class SeedResolution:
    track: Track | None
    candidates: list[Track]
    status: SeedStatus
    title_matches: bool = False


def original_hint(seed: str, seed_artist: str | None = None) -> tuple[str, tuple[str, ...]] | None:
    query = normalize_text(seed)
    for canonical_title, aliases in ORIGINAL_HINTS.items():
        # A translated title is not globally unique: e.g. Nat King Cole also has
        # "I Miss You So". Apply that hint only with the verified artist context.
        known_titles = TITLE_ALIASES.get(canonical_title, (canonical_title,))
        artist_confirmed = (seed_artist is not None and
                            artist_identity(seed_artist) == artist_identity(aliases[0]))
        if (query == normalize_text(canonical_title)
                or (artist_confirmed and query in {normalize_text(title) for title in known_titles})
                or any(
            query in (normalize_text(f"{title} {alias}"), normalize_text(f"{alias} {title}"),
                      normalize_text(f"{title} by {alias}"))
            for title in known_titles for alias in aliases)):
            return canonical_title, aliases
    return None


def recording_title(title: str) -> str:
    title = unicodedata.normalize("NFKC", title)
    # Chinese suffixes can contain the original artist before the version marker.
    for index, character in enumerate(title):
        if index > 0 and character in "([" and _ALTERNATE.search(title[index:]):
            title = title[:index]
            break
    title = _FEATURED.sub("", _NAMED_VERSION.sub("", _VERSION.sub("", title)))
    voice_version = _VOICE_VERSION.search(title)
    if voice_version and voice_version.start() > 0:
        title = title[:voice_version.start()]
    return normalize_text(title.strip())


def is_alternate(track: Track) -> bool:
    def labelled_version(value: str) -> bool:
        value = unicodedata.normalize("NFKC", value)
        # Words such as "Live" or "Cover" in a song/album name are not evidence of
        # an alternate recording; only an explicit qualifier or version tag is.
        if any(match.start() > 0 and _ALTERNATE.search(match.group())
               for match in re.finditer(r"[\[(][^\])]+[)\]]", value)):
            return True
        parts = re.split(r"\s*[-–—]\s*", value, maxsplit=1)
        return len(parts) > 1 and bool(_ALTERNATE.search(parts[1]))

    voice_version = _VOICE_VERSION.search(unicodedata.normalize("NFKC", track.title))
    return (labelled_version(track.title)
            or bool(voice_version and voice_version.start() > 0)
            or bool(track.album and labelled_version(track.album.name))
            or any(normalize_text(tag) in _EXPLICIT_TAGS for tag in track.tags))


def title_matches_query(seed: str, title: str, artist: str,
                        seed_artist: str | None = None) -> bool:
    query, title = normalize_text(seed), recording_title(title)
    hint = original_hint(seed, seed_artist)
    hinted_titles = {normalize_text(value) for value in TITLE_ALIASES.get(hint[0], (hint[0],))} if hint else set()
    if query == title or title in hinted_titles:
        return True
    aliases = artist_aliases(artist)
    return any(query in (normalize_text(f"{title} {artist}"), normalize_text(f"{artist} {title}"),
                        normalize_text(f"{title} by {artist}"))
               for artist in aliases)


def resolve_seed(seed: str, tracks: list[Track], seed_artist: str | None = None) -> SeedResolution:
    title_matches = [track for track in tracks if title_matches_query(
        seed, track.title, track.artist.name, seed_artist)]
    hint = original_hint(seed, seed_artist)
    expected_artist = seed_artist or (hint[1][0] if hint else None)
    candidates = [candidate.track for candidate in deduplicate([
                    track for track in title_matches if not is_alternate(track)])
                  if (expected_artist is None or
                       artist_identity(candidate.track.artist.name) == artist_identity(expected_artist))]
    # Provider aliases and duplicate releases are one choice, never false ambiguity.
    artists: dict[str, Track] = {}
    for candidate in candidates:
        artists.setdefault(artist_identity(candidate.artist.name), candidate)
    choices = list(artists.values())
    if len(choices) == 1:
        return SeedResolution(choices[0], choices, "matched", bool(title_matches))
    return SeedResolution(None, choices[:5], "ambiguous" if choices else "unresolved", bool(title_matches))


def related_factors(seed: Track, track: Track) -> dict[str, float]:
    seed_genres = {normalize_text(value) for value in seed.genres if value.strip()}
    seed_tags = {normalize_text(value) for value in seed.tags if value.strip()}
    genres = {normalize_text(value) for value in track.genres}
    tags = {normalize_text(value) for value in track.tags}
    return {
        "seed_artist": float(artist_identity(seed.artist.name) == artist_identity(track.artist.name)),
        "seed_genre": len(seed_genres & genres) / len(seed_genres) if seed_genres else 0.0,
        "seed_tag": len(seed_tags & tags) / len(seed_tags) if seed_tags else 0.0,
        "seed_language": float(bool(seed.language) and
                               normalize_text(seed.language) == normalize_text(track.language or "")),
    }


def _same_seed_title(seed: Track, track: Track) -> bool:
    title, candidate_title = recording_title(seed.title), recording_title(track.title)
    if title == candidate_title:
        return True
    for canonical_title, artists in ORIGINAL_HINTS.items():
        aliases = {normalize_text(value) for value in TITLE_ALIASES.get(canonical_title, (canonical_title,))}
        if (artist_identity(seed.artist.name) == artist_identity(artists[0])
                and title in aliases and candidate_title in aliases):
            return True
    return False


def rank_related(candidates: list[Candidate], seed: Track,
                 profile: PreferenceProfile) -> list[RankedTrack]:
    related = [candidate for candidate in candidates
               if not _same_seed_title(seed, candidate.track)
               and not is_alternate(candidate.track)
               and any(value > 0 for key, value in related_factors(seed, candidate.track).items()
                       if key != "seed_language")]
    output = []
    # The existing profile/popularity/source policy remains authoritative alongside explicit
    # seed-context weights; the input title itself cannot reward repeated recordings.
    for item in rank(related, "", profile):
        factors = related_factors(seed, item.track)
        breakdown = {**item.score_breakdown,
                     **{name: round(value * SEED_WEIGHTS[name], 6) for name, value in factors.items()}}
        reasons = []
        for name, reason in (("seed_artist", "same artist as your seed"),
                             ("seed_genre", "shares a genre with your seed"),
                             ("seed_tag", "shares a tag with your seed"),
                             ("seed_language", "same language as your seed")):
            if factors[name] > 0:
                reasons.append(reason)
        if item.explanation != "Available from the catalog.":
            reasons.append(item.explanation)
        output.append(RankedTrack(item.key, item.track, item.provenance,
                                  round(sum(breakdown.values()), 6), breakdown, "; ".join(reasons)))
    return sorted(output, key=lambda item: (-item.score, item.key))
