"""Verify runtime fixtures and package boundaries in a built wheel."""

import sys
from pathlib import Path
from zipfile import ZipFile


def main():
    wheel = next(Path(sys.argv[1]).glob("music_recommendation_api-*.whl"))
    with ZipFile(wheel) as archive:
        names = archive.namelist()
        for fixture in ("app/domain/fixtures/recommendations.json", "app/domain/fixtures/evaluation_v1.json",
                        "app/rag/fixtures/music_v1.json"):
            assert fixture in names, f"Missing runtime fixture: {fixture}"
        assert not any(name.startswith(("tests/", "migrations/")) for name in names)
    print("Wheel runtime fixtures and package boundaries: passed")


if __name__ == "__main__":
    main()
