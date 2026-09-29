from __future__ import annotations

import os
import re
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


DEVICE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{16,128}$")
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]


class RecommendationRequest(BaseModel):
    seed: str = Field(min_length=1, max_length=120)
    limit: int = Field(default=10, ge=1, le=20)
    language: Literal["ANY", "ZH", "EN", "JA", "KO", "INSTRUMENTAL"] = "ANY"


class RecommendationItem(BaseModel):
    id: str
    title: str
    artist: str
    language: str
    source: Literal["CATALOG"]
    explanation: str


class RecommendationResponse(BaseModel):
    request_id: str = Field(serialization_alias="requestId")
    items: list[RecommendationItem]


CATALOG: tuple[tuple[str, str, str], ...] = (
    ("qingtian", "晴天", "周杰伦"),
    ("qilixiang", "七里香", "周杰伦"),
    ("daoxiang", "稻香", "周杰伦"),
    ("yequ", "夜曲", "周杰伦"),
)


def require_device_id(
    x_device_id: Annotated[str | None, Header(alias="X-Device-Id")] = None,
) -> str:
    if x_device_id is None or not DEVICE_ID_PATTERN.fullmatch(x_device_id):
        raise HTTPException(status_code=422, detail="A valid X-Device-Id header is required.")
    return x_device_id


def create_app() -> FastAPI:
    api = FastAPI(title="Music Recommendation API", version="0.1.0")
    api.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-Device-Id"],
    )

    @api.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "music-recommendation-api"}

    @api.post("/v1/recommendations", response_model=RecommendationResponse)
    def recommend(
        payload: RecommendationRequest,
        _: Annotated[str, Depends(require_device_id)],
    ) -> RecommendationResponse:
        normalized_seed = payload.seed.casefold().strip()
        matched = [song for song in CATALOG if normalized_seed in f"{song[1]} {song[2]}".casefold()]
        candidates = matched + [song for song in CATALOG if song not in matched]
        items = [
            RecommendationItem(
                id=song_id,
                title=title,
                artist=artist,
                language="ZH",
                source="CATALOG",
                explanation=f"Matches the initial catalog for the seed ‘{payload.seed}’." if matched
                else f"A discovery fallback for the seed ‘{payload.seed}’.",
            )
            for song_id, title, artist in candidates[: payload.limit]
        ]
        return RecommendationResponse(request_id=str(uuid4()), items=items)

    return api


app = create_app()
