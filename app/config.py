"""Load Erez-owned YAML and prompts, plus env vars. Fails loudly on bad input."""

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

PLATFORMS = {"instagram", "tiktok", "youtube"}


@dataclass(frozen=True)
class Creator:
    platform: str
    handle: str


@dataclass(frozen=True)
class Discovery:
    """/discover: which hashtags to hunt new creators with, and the size floor."""

    hashtags: list[str] = field(default_factory=list)
    min_subscribers: int = 10_000


@dataclass(frozen=True)
class Watchlist:
    creators: list[Creator]
    topics: list[str]
    discovery: Discovery = field(default_factory=Discovery)


def load_watchlist(path: str = "config/watchlist.yaml") -> Watchlist:
    """Read Erez's creator list. A typo here should fail now, not at 07:00."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ValueError(f"Watchlist in {path} must be a YAML mapping")
    creators = []
    for entry in data.get("creators") or []:
        platform = str(entry["platform"]).lower()
        if platform not in PLATFORMS:
            raise ValueError(
                f"Unknown platform {platform!r} in {path}. Use one of: {sorted(PLATFORMS)}"
            )
        creators.append(Creator(platform=platform, handle=str(entry["handle"])))
    topics = [str(t) for t in (data.get("topics") or [])]
    disc = data.get("discovery") or {}
    discovery = Discovery(
        hashtags=[str(h) for h in (disc.get("hashtags") or [])],
        min_subscribers=int(disc.get("min_subscribers", 10_000)),
    )
    return Watchlist(creators=creators, topics=topics, discovery=discovery)


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


def load_prompts(*names: str) -> str:
    """Several prompt files joined into one. The model only sees what we send it —
    a prompt that *mentions* another file (like editing_tips.md) must be sent
    together with it, or the reference points at nothing."""
    return "\n\n---\n\n".join(load_prompt(name) for name in names)


def env(key: str, default: str | None = None) -> str:
    value = os.environ.get(key, default)
    if value is None:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return value
