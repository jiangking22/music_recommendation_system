import hashlib
import math

from app.domain.music import Track, normalize_text
from app.domain.profile import PreferenceProfile

DIMENSIONS = 16


def _embed(weighted_terms: list[tuple[str, float]]) -> list[float]:
    vector = [0.0] * DIMENSIONS
    for term, weight in weighted_terms:
        digest = hashlib.sha256(term.encode("utf-8")).digest()
        bucket = int.from_bytes(digest[:4], "big") % DIMENSIONS
        sign = 1 if digest[4] % 2 == 0 else -1
        vector[bucket] += sign * weight
    norm = math.sqrt(sum(value * value for value in vector))
    return [round(value / norm, 8) for value in vector] if norm else vector


def embed_song(track: Track) -> list[float]:
    terms = [(f"title:{token}", 0.5) for token in normalize_text(track.title).split()]
    terms += [(f"artist:{normalize_text(track.artist.name)}", 1.0)]
    terms += [(f"genre:{normalize_text(genre)}", 1.0) for genre in track.genres]
    terms += [(f"tag:{normalize_text(tag)}", 0.8) for tag in track.tags]
    if track.language:
        terms.append((f"language:{normalize_text(track.language)}", 0.6))
    return _embed(terms)


def embed_user(profile: PreferenceProfile) -> list[float]:
    terms = []
    for kind, affinity in (("artist", profile.artist_affinity), ("genre", profile.genre_affinity),
                           ("tag", profile.tag_affinity), ("language", profile.language_affinity)):
        terms.extend((f"{kind}:{key}", weight) for key, weight in sorted(affinity.items()))
    return _embed(terms)


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != DIMENSIONS or len(right) != DIMENSIONS:
        raise ValueError("Embedding dimension mismatch.")
    if left == right:
        return 1.0 if any(left) else 0.0
    norm = math.sqrt(sum(value * value for value in left) * sum(value * value for value in right))
    return round(sum(a * b for a, b in zip(left, right, strict=True)) / norm, 6) if norm else 0.0
