import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class FixtureSong:
    id: str
    title: str
    artist: str
    tags: tuple[str, ...]


@lru_cache
def fixture_songs() -> tuple[FixtureSong, ...]:
    fixture = Path(__file__).parent / "fixtures" / "recommendations.json"
    rows = json.loads(fixture.read_text(encoding="utf-8"))
    return tuple(FixtureSong(id=row["id"], title=row["title"], artist=row["artist"], tags=tuple(row["tags"])) for row in rows)
