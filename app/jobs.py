"""The 07:00 job, and the switch that tells us when it didn't run.

A digest that fails silently is worse than one that fails loudly: Erez just stops
trusting the bot. Every failure path here either degrades with an explanation or
pages Elik.
"""

import logging

from app.analyze import gemini
from app.digest import page, rank
from app.store import usage, videos

log = logging.getLogger(__name__)


def _collect_all(sources, watchlist, *, since: str) -> list:
    """Gather from every source. A dead vendor loses its results, not the morning."""
    found = []
    for source in sources:
        try:
            found.extend(source.collect(watchlist, since=since))
        except Exception:
            log.exception("Source %s failed; continuing without it", source.name)
    return found


def _analyze_candidate(candidate, *, deps) -> dict | None:
    cached = videos.get_analysis(deps.conn, candidate.id, gemini.RUBRIC_VERSION)
    if cached:
        return cached
    try:
        result = deps.download(candidate.url, deps.work_dir)
    except Exception:
        log.warning("Could not download %s; skipping", candidate.url)
        return None

    analyze = deps.analyze or gemini.analyze_video
    analysis = analyze(result.path, deps.rubric, deps.gemini_client)
    videos.save_analysis(deps.conn, candidate.id, gemini.RUBRIC_VERSION, analysis, now=deps.now())
    usage.record(
        deps.conn,
        "gemini",
        "analyze_video",
        1,
        gemini.estimate_cost(result.duration_seconds),
        now=deps.now(),
    )
    return analysis


def run_digest(
    *, deps, sources, notifier, settings, watchlist, compose_digest, template, now: str
) -> str | None:
    """Collect, rank, analyze, compose, publish, send. Returns the body, or None."""
    for_date = now[:10]
    candidates = _collect_all(sources, watchlist, since=_since(now, settings))
    picked = rank.top_n(candidates, n=settings["digest"]["max_videos"], now=now)

    items = []
    for candidate in picked:
        videos.upsert_video(deps.conn, candidate.as_row(), now=now)
        analysis = _analyze_candidate(candidate, deps=deps)
        if analysis:
            items.append({**candidate.as_row(), "analysis": analysis})

    if not items:
        notifier.send("בוקר טוב ☕ לא מצאתי הבוקר משהו ששווה לדבר עליו. אליק יבדוק.")
        log.warning("Digest for %s had no analyzable items", for_date)
        return None

    body = compose_digest(items, template, deps.claude_client)
    html_path = page.write(page.render(body, items, for_date=for_date), "web/out", for_date)

    # Send first: if delivery raises, sent_at is never written, so the 07:30 dead-man's-switch
    # fires instead of silently believing the digest went out.
    notifier.send(body)
    deps.conn.execute(
        """
        INSERT INTO digests (for_date, body_he, html_path, sent_at, created_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(for_date) DO UPDATE SET
            body_he = excluded.body_he, html_path = excluded.html_path,
            sent_at = excluded.sent_at
        """,
        (for_date, body, html_path, now, now),
    )
    deps.conn.commit()
    return body


def _since(now: str, settings: dict) -> str:
    from datetime import datetime, timedelta

    parsed = datetime.strptime(now, "%Y-%m-%dT%H:%M:%SZ")
    hours = settings["collect"]["lookback_hours"]
    return (parsed - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")


def deadman_check(*, conn, admin_notifier, for_date: str, now: str) -> None:
    """Runs at 07:30. If no digest went out, Elik hears about it before Erez does."""
    row = conn.execute("SELECT sent_at FROM digests WHERE for_date = ?", (for_date,)).fetchone()
    if row and row["sent_at"]:
        return
    admin_notifier.send(f"⚠️ No digest went out for {for_date}. Check the logs.")
    log.error("Dead-man's-switch fired for %s", for_date)
