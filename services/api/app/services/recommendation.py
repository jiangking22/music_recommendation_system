from app.domain.recommendation import FixtureSong, recommend_fixture


def recommend(seed: str, limit: int) -> list[FixtureSong]:
    return recommend_fixture(seed, limit)
