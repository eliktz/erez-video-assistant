"""Read and write videos and their analyses. Every analysis is kept — the corpus compounds."""

import json
import sqlite3

_FIELDS = (
    "id, platform, native_id, url, creator, caption, posted_at, "
    "views, likes, comments, source, first_seen_at, updated_at"
)


def upsert_video(conn: sqlite3.Connection, video: dict, now: str) -> str:
    """Insert a video, or refresh its metrics if we have seen it before.

    first_seen_at is never overwritten — velocity scoring depends on it.
    """
    conn.execute(
        """
        INSERT INTO videos (id, platform, native_id, url, creator, caption, posted_at,
                            views, likes, comments, source, first_seen_at, updated_at)
        VALUES (:id, :platform, :native_id, :url, :creator, :caption, :posted_at,
                :views, :likes, :comments, :source, :now, :now)
        ON CONFLICT(id) DO UPDATE SET
            views = excluded.views,
            likes = excluded.likes,
            comments = excluded.comments,
            caption = excluded.caption,
            updated_at = excluded.updated_at
        """,
        {**video, "now": now},
    )
    conn.commit()
    return video["id"]


def get_video(conn: sqlite3.Connection, video_id: str) -> dict | None:
    row = conn.execute(f"SELECT {_FIELDS} FROM videos WHERE id = ?", (video_id,)).fetchone()
    return dict(row) if row else None


def known_ids(conn: sqlite3.Connection, ids: list[str]) -> set[str]:
    """Which of these video ids do we already have? Used to skip re-analysis."""
    if not ids:
        return set()
    placeholders = ",".join("?" * len(ids))
    rows = conn.execute(f"SELECT id FROM videos WHERE id IN ({placeholders})", ids).fetchall()
    return {r["id"] for r in rows}


def save_analysis(
    conn: sqlite3.Connection, video_id: str, rubric_version: str, payload: dict, now: str
) -> None:
    conn.execute(
        """
        INSERT INTO analyses (video_id, rubric_version, payload_json, created_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(video_id, rubric_version) DO UPDATE SET
            payload_json = excluded.payload_json,
            created_at = excluded.created_at
        """,
        (video_id, rubric_version, json.dumps(payload, ensure_ascii=False), now),
    )
    conn.commit()


def get_analysis(conn: sqlite3.Connection, video_id: str, rubric_version: str) -> dict | None:
    row = conn.execute(
        "SELECT payload_json FROM analyses WHERE video_id = ? AND rubric_version = ?",
        (video_id, rubric_version),
    ).fetchone()
    return json.loads(row["payload_json"]) if row else None


def recent_analyses(conn: sqlite3.Connection, limit: int = 10) -> list[dict]:
    """The last N analyses, newest first — what /idea pitches ideas from."""
    rows = conn.execute(
        "SELECT payload_json FROM analyses ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [json.loads(row["payload_json"]) for row in rows]
