"""Project configuration and paths, loaded from config.yaml at the repo root."""
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


@lru_cache
def load() -> dict:
    with open(ROOT / "config.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def path(key: str) -> Path:
    return ROOT / load()["paths"][key]


def seasons() -> list[int]:
    s = load()["seasons"]
    return list(range(s["first"], s["current"] + 1))


def current_season() -> int:
    return load()["seasons"]["current"]


def season_label(year: int) -> str:
    return f"{year}/{(year + 1) % 100:02d}"
