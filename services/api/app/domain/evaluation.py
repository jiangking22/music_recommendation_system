import json
from pathlib import Path

from app.domain.music import (
    Artist,
    ProviderSource,
    Track,
    canonical_key,
    normalize_text,
)
from app.domain.pipeline import deduplicate, rank, rerank_diverse
from app.domain.profile import PreferenceProfile


def evaluate() -> dict[str, float | str | int]:
    fixture = Path(__file__).parent / "fixtures" / "evaluation_v1.json"
    data = json.loads(fixture.read_text(encoding="utf-8"))
    tracks = [Track(title=row["title"], artist=Artist(name=row["artist"]),
                    source=ProviderSource(provider=row["provider"], provider_track_id=row["id"]),
                    canonical_key=canonical_key(row["title"], row["artist"]),
                    genres=row["genres"], tags=row["tags"], language=row["language"])
              for row in data["catalog"]]
    candidates = deduplicate(tracks)
    relevance, lift, diversity, shown = [], [], [], set()
    for case in data["cases"]:
        profile = PreferenceProfile(artist_affinity={normalize_text(case["liked_artist"]): 1.0})
        personalized = rerank_diverse(rank(candidates, case["seed"], profile), case["limit"])
        ids = [item.track.source.provider_track_id for item in personalized]
        shown.update(ids)
        relevance.append(sum(item in case["relevant"] for item in ids) / len(ids))
        # Full ranked positions measure the preferred item's movement even if it falls below the cutoff.
        full_base = [item.track.source.provider_track_id for item in rank(candidates, case["seed"], PreferenceProfile())]
        full_personal = [item.track.source.provider_track_id for item in rank(candidates, case["seed"], profile)]
        lift.append(full_base.index(case["preferred"]) - full_personal.index(case["preferred"]))
        diversity.append((len({item.track.artist.name for item in personalized})
                          + len({item.track.source.provider for item in personalized})
                          + len({tuple(item.track.genres) for item in personalized})) / (3 * len(ids)))
    return {
        "version": data["version"],
        "cases": len(data["cases"]),
        "relevance": round(sum(relevance) / len(relevance), 4),
        "personalization_effect": round(sum(lift) / len(lift), 4),
        "diversity": round(sum(diversity) / len(diversity), 4),
        "coverage": round(len(shown) / len(candidates), 4),
    }


if __name__ == "__main__":
    print(json.dumps(evaluate(), sort_keys=True))
