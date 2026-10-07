"""Recording-bound listening evidence; absence of metadata is unknown."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.music import Track, normalize_text

LANGUAGES = {
    "zh": {"zh", "zh cn", "zh tw", "chinese", "mandarin", "cantonese", "国语", "华语", "中文", "mandopop", "cantopop"},
    "en": {"en", "en us", "en gb", "english", "英语", "英文"},
}
VOCALS = {
    "instrumental": {"instrumental", "instrumental music", "纯音乐", "器乐", "伴奏", "karaoke"},
    "vocal": {"vocal", "vocals", "vocal music", "人声", "带人声"},
}
FEELS = {'calm': {'calm', 'soft', 'mellow', 'relaxing', '舒缓', '松弛'},
         'sad': {'sad', 'emo', '伤感'}, 'energetic': {'energetic', 'upbeat', '活力'}}

class AttributeEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    track_id: str = Field(min_length=1, max_length=450)
    attribute: Literal["language", "vocals", "feel"]
    value: str | None = Field(default=None, max_length=40)
    origin: Literal["provider", "model", "web"]
    basis: str = Field(min_length=1, max_length=300)
    source_url: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def supported_value(self):
        accepted = {"language": {"zh", "en"}, "vocals": {"vocal", "instrumental"},
                    "feel": {"calm", "sad", "energetic"}}
        if self.value is not None and self.value not in accepted[self.attribute]:
            raise ValueError("Unsupported listening attribute")
        return self

class ListeningConstraints(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    language: Literal["zh", "en"] | None = None
    vocals: Literal["vocal", "instrumental"] | None = None
    feel: Literal['calm', 'sad', 'energetic'] | None = None

    def assess(self, track: Track, evidence: list[AttributeEvidence] | None = None) -> Literal["match", "mismatch", "unknown"]:
        labels = {normalize_text(value) for value in (*track.tags, *track.genres)}
        language = normalize_text(track.language or "")
        states = []
        for attribute, wanted in self.model_dump().items():
            if wanted is None:
                continue
            vocabulary = LANGUAGES if attribute == "language" else VOCALS if attribute == 'vocals' else FEELS
            values = {value for value, aliases in vocabulary.items() if labels & aliases or (
                attribute == "language" and language in aliases)}
            if attribute == "language" and language and not values:
                values.add("other")
            supplied = [row for row in (evidence or []) if row.track_id == track.canonical_key
                        and row.attribute == attribute and row.value is not None]
            values |= {row.value for row in supplied if row.origin in ("provider", "web")}
            if not values:
                values = {row.value for row in supplied if row.origin == "model"}
            states.append("unknown" if not values else "match" if values == {wanted} else "mismatch")
        if "mismatch" in states:
            return "mismatch"
        return "unknown" if "unknown" in states else "match"

    def matches(self, track: Track, evidence: list[AttributeEvidence] | None = None) -> bool:
        return self.assess(track, evidence) == "match"
