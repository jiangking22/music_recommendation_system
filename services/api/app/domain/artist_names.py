"""Small, reviewed artist aliases; display enrichment never changes catalog identity."""

from dataclasses import dataclass

from app.domain.music import Track, normalize_text


@dataclass(frozen=True)
class ArtistNames:
    preferred_name: str
    aliases: tuple[str, ...]
    sources: tuple[str, ...]


# Reviewed sources belong to each entry. Model output and user feedback never register aliases.
_ARTISTS = (
    ArtistNames("王菲", ("王菲", "Faye Wong"), (
        "https://music.apple.com/cn/album/966805714",
        "https://music.apple.com/us/album/966805714",
    )),
    ArtistNames("苏打绿", ("苏打绿", "蘇打綠", "sodagreen", "Soda Green"), (
        "https://www.sonymusic.com.tw/artist/sodagreen/",
        "https://music.apple.com/cn/playlist/pl.e441d462104340d68c456858eec0b08d",
    )),
    ArtistNames("周杰伦", ("周杰伦", "周杰倫", "Jay Chou"), (
        "https://www.jvrmusic.com.tw/artist/profile/1150822038412333056",
        "https://music.apple.com/cn/multi-room/1537748057",
    )),
    ArtistNames("林俊杰", ("林俊杰", "林俊傑", "JJ Lin"), (
        "https://www.warnermusic.com.tw/pages/-%E6%9E%97%E4%BF%8A%E5%82%91",
        "https://music.apple.com/cn/playlist/pl.92e5bbee7ab6458bbb21a83f0ab7adeb",
    )),
    ArtistNames("陈奕迅", ("陈奕迅", "陳奕迅", "Eason Chan"), (
        "https://www.youtube.com/watch?v=bvZ-qeZdrr0",  # Universal Music HK official channel
        "https://music.apple.com/cn/song/1831491094",
    )),
    ArtistNames("刘若英", ("刘若英", "劉若英", "Rene Liu", "René Liu"), (
        "https://www.bin-music.com.tw/artist",
        "https://music.apple.com/us/artist/rene-liu/16027938",
        "https://music.apple.com/us/playlist/pl.0b420a02b5f54d5790c1f751d2bc842f?l=zh-Hans-CN",
    )),
    ArtistNames("冯提莫", ("冯提莫", "馮提莫", "TimoFeng", "Feng Timo"), (
        "https://music.apple.com/us/artist/timofeng/1194941620",
        "https://open.spotify.com/artist/6lErCMDS7E9Dv2oo8uVDnP",  # Artist's Chinese self-description
    )),
    ArtistNames("Taylor Swift", ("Taylor Swift", "泰勒·斯威夫特", "泰勒絲"), (
        "https://www.umusic.com.cn/index.php?c=category&id=25",
        "https://www.umusic.com.tw/album.php?q=N2T0g216M-Q1E9AE0E9AE-",
    )),
)
_BY_ALIAS = {normalize_text(alias): entry for entry in _ARTISTS for alias in entry.aliases}


def artist_identity(name: str) -> str:
    """Resolve reviewed aliases for matching, without replacing persisted track keys."""
    entry = _BY_ALIAS.get(normalize_text(name))
    return normalize_text(entry.preferred_name if entry else name)


def preferred_artist_name(name: str) -> str:
    """Use a reviewed preferred spelling; preserve names without verified aliases verbatim."""
    entry = _BY_ALIAS.get(normalize_text(name))
    return entry.preferred_name if entry else name


def artist_aliases(name: str) -> tuple[str, ...]:
    entry = _BY_ALIAS.get(normalize_text(name))
    return entry.aliases if entry else (name,)


def enrich_track(track: Track) -> Track:
    """Attach a trusted display label while retaining source names, IDs and canonical keys."""
    entry = _BY_ALIAS.get(normalize_text(track.artist.name))
    artist = track.artist.model_copy(update={"display_name": entry.preferred_name if entry else None})
    return track.model_copy(update={"artist": artist})
