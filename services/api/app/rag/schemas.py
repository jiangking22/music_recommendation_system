from typing import Literal

from pydantic import BaseModel, ConfigDict


class Citation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    document_id: str
    title: str
    category: Literal["artist", "genre", "album", "explanation"]
    chunk_id: str
    text: str
    score: float
