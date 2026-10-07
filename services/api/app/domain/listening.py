"""Optional listening constraints use supplied catalog metadata, never model guesses."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.domain.music import Track, normalize_text


class ListeningConstraints(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    language: Literal["zh", "en"] | None = None
    vocals: Literal["vocal", "instrumental"] | None = None

    def matches(self, track: Track) -> bool:
        labels = {normalize_text(value) for value in (*track.tags, *track.genres)}
        language = normalize_text(track.language or "")
        aliases = {"zh": {"zh", "zh cn", "zh tw", "chinese", "mandarin", "cantonese", "国语", "华语", "中文"},
                   "en": {"en", "en us", "en gb", "english", "英语", "英文"}}
        if self.language and language not in aliases[self.language] and not labels & aliases[self.language]:
            return False
        instrumental = bool(labels & {"instrumental", "instrumental music", "纯音乐", "器乐", "伴奏"})
        vocal = bool(labels & {"vocal", "vocals", "vocal music", "人声", "带人声"})
        if self.vocals == "vocal" and (not vocal or instrumental):
            return False
        return not (self.vocals == "instrumental" and (not instrumental or vocal))
