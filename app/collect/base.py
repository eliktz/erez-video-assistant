"""The vendor seam.

Scrapers break and reprice. Everything downstream talks to Candidate and Source,
so replacing a vendor means one new file in this folder and nothing else.
"""

from dataclasses import asdict, dataclass
from typing import Protocol

from app.config import Watchlist


@dataclass(frozen=True)
class Candidate:
    id: str
    platform: str
    native_id: str
    url: str
    creator: str | None
    caption: str | None
    posted_at: str | None
    views: int | None
    likes: int | None
    comments: int | None
    source: str

    def as_row(self) -> dict:
        """Shape the store expects."""
        return asdict(self)


class Source(Protocol):
    name: str

    def collect(self, watchlist: Watchlist, *, since: str) -> list[Candidate]:
        """Public, logged-out data only. Never Erez's account."""
        ...
