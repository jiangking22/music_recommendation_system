import json
import math

from sqlalchemy.types import UserDefinedType

from app.domain.embedding import DIMENSIONS


class Vector16(UserDefinedType):
    cache_ok = True

    def get_col_spec(self, **_kwargs: object) -> str:
        return f"vector({DIMENSIONS})"

    def bind_processor(self, _dialect):
        def process(value: list[float] | None) -> str | None:
            if value is None:
                return None
            if (len(value) != DIMENSIONS or any(not isinstance(item, (int, float))
                                               or not math.isfinite(item) for item in value)):
                raise ValueError("Expected a 16-dimensional numeric vector.")
            return json.dumps(value, separators=(",", ":"))
        return process

    def result_processor(self, _dialect, _coltype):
        def process(value: str | None) -> list[float] | None:
            return json.loads(value) if value is not None else None
        return process
