"""Pick the videos worth spending analysis money on.

Raw view count rewards old videos. Views-per-hour surfaces what is climbing right
now, which is what "burning up the networks" actually means.
"""

from datetime import datetime

from app.collect.base import Candidate

_MIN_AGE_HOURS = 0.5  # a video minutes old would otherwise score infinity


def _parse(ts: str) -> datetime:
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")


def velocity(candidate: Candidate, *, now: str) -> float:
    """Views per hour since posting. 0.0 when we lack the data to know."""
    if not candidate.views or not candidate.posted_at:
        return 0.0
    age_hours = (_parse(now) - _parse(candidate.posted_at)).total_seconds() / 3600
    return candidate.views / max(age_hours, _MIN_AGE_HOURS)


def top_n(candidates: list[Candidate], *, n: int, now: str) -> list[Candidate]:
    """Highest-velocity candidates, one row per video."""
    unique = {c.id: c for c in candidates}
    ranked = sorted(unique.values(), key=lambda c: velocity(c, now=now), reverse=True)
    return ranked[:n]
