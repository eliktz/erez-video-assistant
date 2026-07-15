"""Every paid API call lands here, so /costs can answer before the bill does."""

import sqlite3


def record(
    conn: sqlite3.Connection,
    provider: str,
    operation: str,
    units: float,
    cost_usd: float,
    now: str,
) -> None:
    conn.execute(
        """
        INSERT INTO provider_usage (provider, operation, units, cost_usd, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (provider, operation, units, cost_usd, now),
    )
    conn.commit()


def month_to_date(conn: sqlite3.Connection, month: str) -> list[dict]:
    """Spend per provider for a month. `month` is 'YYYY-MM'."""
    rows = conn.execute(
        """
        SELECT provider,
               ROUND(SUM(cost_usd), 4) AS cost_usd,
               COUNT(*) AS calls
        FROM provider_usage
        WHERE substr(created_at, 1, 7) = ?
        GROUP BY provider
        ORDER BY cost_usd DESC
        """,
        (month,),
    ).fetchall()
    return [dict(r) for r in rows]
