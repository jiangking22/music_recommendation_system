from __future__ import annotations

import re
import os
from typing import Annotated

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware


DEVICE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{16,128}$")

allowed_origins = [origin.strip() for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",") if origin.strip()]

app = FastAPI(title="Music Recommendation API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["GET"],
    allow_headers=["X-Device-Id"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "music-recommendation-api"}


@app.get("/v1/device")
def get_device(x_device_id: Annotated[str | None, Header(alias="X-Device-Id")] = None) -> dict[str, str]:
    if x_device_id is None or not DEVICE_ID_PATTERN.fullmatch(x_device_id):
        raise HTTPException(status_code=422, detail="A valid X-Device-Id header is required.")
    return {"deviceId": x_device_id}
