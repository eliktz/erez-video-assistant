"""Erez replies to a bot message — the bot continues that thread.

This is what makes /idea a brainstorm instead of a one-shot answer (Erez,
2026-07-23): he replies "תפתח רעיון 2" on the ideas list and the bot develops
that idea. Telegram's reply_to_message carries the full quoted text, so the
context rides on the message itself — no conversation memory, no new table.
"""

from app import bot
from app.digest import compose
from app.store import usage


def quoted_bot_text(message, bot_id: int) -> str | None:
    """The text of the bot's own message this one replies to — or None.

    None means "this is not a follow-up": not a reply at all, or a reply to a
    human. In the group that distinction is the whole feature — Erez and Elik
    talking to each other must never trigger the bot.
    """
    replied = getattr(message, "reply_to_message", None) if message else None
    if replied is None or replied.from_user is None:
        return None
    if replied.from_user.id != bot_id:
        return None
    return replied.text or ""


def continue_thread(deps, *, quoted: str, reply: str, template: str, compose_fn=None) -> str:
    """One constrained drafting call with the quoted context. Billed like the rest."""
    if bot.over_budget(deps.conn, deps.monthly_cap_usd, deps.now()[:7]):
        return "עברנו את תקרת ההוצאה החודשית. תגיד לאליק שיעלה אותה."
    write = compose_fn or compose.continue_thread
    written = write(quoted, reply, template, deps.gemini_client)
    usage.record(deps.conn, "gemini", "follow_up", 1, written.cost_usd, now=deps.now())
    return written.text
