"""Load Erez-owned YAML and prompts, plus env vars. Fails loudly on bad input."""

import os
from dataclasses import dataclass
from pathlib import Path

import yaml

PLATFORMS = {"instagram", "tiktok", "youtube"}


@dataclass(frozen=True)
class Creator:
    platform: str
    handle: str


@dataclass(frozen=True)
class Watchlist:
    creators: list[Creator]
    topics: list[str]


def load_watchlist(path: str = "config/watchlist.yaml") -> Watchlist:
    """Read Erez's creator list. A typo here should fail now, not at 07:00."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    creators = []
    for entry in data.get("creators") or []:
        platform = str(entry["platform"]).lower()
        if platform not in PLATFORMS:
            raise ValueError(
                f"Unknown platform {platform!r} in {path}. Use one of: {sorted(PLATFORMS)}"
            )
        creators.append(Creator(platform=platform, handle=str(entry["handle"])))
    topics = [str(t) for t in (data.get("topics") or [])]
    return Watchlist(creators=creators, topics=topics)


def load_settings(path: str = "config/settings.yaml") -> dict:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"Settings in {path} must be a YAML mapping")
    return data


def load_prompt(name: str) -> str:
    """Read prompts/{name}.md. All Hebrew lives there — never inline in code."""
    return Path(f"prompts/{name}.md").read_text(encoding="utf-8")


def env(key: str, default: str | None = None) -> str:
    value = os.environ.get(key, default)
    if value is None:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return value
