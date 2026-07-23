"""/idea: turn recently analyzed videos into concrete ideas for Erez, via Gemini.

Reads what the bot already knows (recent analyses) and pitches ideas from it —
it never re-analyzes or fetches anything new, so this is nearly free to run.
"""

from app.bot import Deps, over_budget
from app.digest import compose
from app.store import usage, videos

_NO_VIDEOS = (
    "עוד לא ניתחתי מספיק סרטונים כדי להציע רעיונות. שלח לי כמה קישורים קודם, או חכה לדוח הבוקר."
)


def pitch(deps: Deps, template: str, *, limit: int = 10) -> str:
    """Recent analyses -> 3 Hebrew video ideas. Returns text safe to send to Erez."""
    if over_budget(deps.conn, deps.monthly_cap_usd, deps.now()[:7]):
        return "עברנו את תקרת ההוצאה החודשית. תגיד לאליק שיעלה אותה."

    analyses = videos.recent_analyses(deps.conn, limit=limit)
    if not analyses:
        return _NO_VIDEOS

    written = compose.pitch_ideas(analyses, template, deps.gemini_client)
    usage.record(deps.conn, "gemini", "pitch_ideas", 1, written.cost_usd, now=deps.now())
    return written.text
