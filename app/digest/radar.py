"""Erez's trend radar — the 2x2 that shapes the morning digest (spec 2026-07-24/25).

|        | emotional — Erez's genre | general — a song, a meme |
| Israel | 3/day, full analysis     | 2/day, one light line    |
| World  | 3/day, full analysis     | 2/day, one light line    |

Each chart video gets ONE rubric call; `fits_erez_style` in the answer picks
the column. General trends get no deep writeup — the rubric does not apply to
a meme — just a "here's what's buzzing" line. Israel and world stay separate
digest sections on purpose: mixing them buries the local signal in the global one.
"""

import logging
from dataclasses import dataclass

from app.digest import rank

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Quotas:
    """How many digest slots each quadrant gets, per region."""

    emotional: int = 3  # full analysis + writeup
    general: int = 2  # one line, no analysis
    probes: int = 5  # max rubric calls per region — every probe is a paid Gemini call


def quotas_from(settings: dict) -> Quotas:
    """Erez tunes these in config/settings.yaml; missing keys fall back to his spec."""
    radar = settings.get("digest", {}).get("radar") or {}
    return Quotas(
        emotional=radar.get("emotional_per_region", 3),
        general=radar.get("general_per_region", 2),
        probes=radar.get("probe_per_region", 5),
    )


def collect_charts(trending: dict, *, excluded) -> dict[str, list]:
    """Every region's chart, minus formats Erez asked to never see.

    A dead chart (API quota, network) loses its section, not the whole morning.
    """
    charts = {}
    for region, source in trending.items():
        try:
            charts[region] = [c for c in source.chart() if not excluded(c)]
        except Exception:
            log.exception("Trending chart %r failed; continuing without it", region)
            charts[region] = []
    return charts


def sort_region(chart: list, *, classify, quotas: Quotas) -> tuple[list, list]:
    """Walk one region's chart top-down and fill its two quadrants.

    classify(candidate) returns the analysis dict, or None when the video could
    not be analyzed (skip it). Emotional keeps (candidate, analysis) pairs;
    general keeps plain candidates — they get no writeup. Stops when both
    quadrants are full or the probe budget runs out: the cap is what keeps the
    radar's daily cost fixed.
    """
    emotional, general = [], []
    for candidate in chart[: quotas.probes]:
        if len(emotional) == quotas.emotional and len(general) == quotas.general:
            break
        analysis = classify(candidate)
        if analysis is None:
            continue
        if analysis.get("fits_erez_style"):
            if len(emotional) < quotas.emotional:
                emotional.append((candidate, analysis))
        elif len(general) < quotas.general:
            general.append(candidate)
    return emotional, general


def pick(charts: dict, pool: list, *, classify, quotas: Quotas, now: str) -> tuple[list, list]:
    """The morning's picks under the 2x2.

    charts: {"israel": [...], "world": [...]} — each region's trending chart.
    pool: the watchlist/topic candidates. They are world emotional-genre by
    construction (that is what the searches look for), so they compete with the
    world chart's emotional finds for the world slots — best velocity wins.

    Returns (deep, light), both as [(candidate, section)] lists: deep gets the
    full analysis + writeup, light is shown as one line each with no analysis.
    A video trending in both regions appears once, under Israel.
    """
    deep, light, taken = [], [], set()
    for section in ("israel", "world"):
        chart = [c for c in charts.get(section, []) if c.id not in taken]
        emotional, general = sort_region(chart, classify=classify, quotas=quotas)
        picks = [c for c, _ in emotional]
        if section == "world":
            fresh = [c for c in pool if c.id not in taken]
            picks = rank.top_n(fresh + picks, n=quotas.emotional, now=now)
        deep += [(c, section) for c in picks]
        light += [(c, section) for c in general]
        taken |= {c.id for c in picks} | {c.id for c in general}
    return deep, light
