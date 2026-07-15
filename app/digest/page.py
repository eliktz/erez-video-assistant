"""Render the digest as a web page.

WhatsApp templates cap at 1024 characters, so the digest can never be the message
itself — it has to be a link. That constraint gave us a better product: a tapped
link opens a real page with the videos in it.
"""

import html
import json
import sys
from pathlib import Path

_TEMPLATE = Path("web/template.html")


def _card(item: dict) -> str:
    analysis = item.get("analysis") or {}
    views = item.get("views")
    views_text = f"{views:,} צפיות · " if views else ""
    return (
        f"""
  <div class="card">
    <div class="meta">{views_text}{html.escape(str(item.get("creator") or ""))}</div>
    <p class="hook">{html.escape(str(analysis.get("hook") or ""))}</p>
    <p class="why">{html.escape(str(analysis.get("why_it_worked") or ""))}</p>
    <div class="idea">💡 {html.escape(str(analysis.get("transferable_idea") or ""))}</div>
    <p><a href="{html.escape(str(item.get("url") or ""))}" target="_blank" rel="noopener">"""
        """לצפייה בסרטון</a></p>
  </div>"""
    )


def render(body_he: str, items: list[dict], *, for_date: str) -> str:
    """Full HTML page. Everything from a vendor is escaped — it is untrusted text."""
    cards = "".join(_card(item) for item in items)
    return (
        _TEMPLATE.read_text(encoding="utf-8")
        .replace("{{DATE}}", html.escape(for_date))
        .replace("{{BODY}}", html.escape(body_he))
        .replace("{{CARDS}}", cards)
    )


def write(html_text: str, out_dir: str, for_date: str) -> str:
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    path = f"{out_dir}/{for_date}.html"
    Path(path).write_text(html_text, encoding="utf-8")
    return path


def _preview() -> None:
    """`make digest-preview` — renders from fixtures. No API keys, no cost, no network."""
    items = json.loads(Path("tests/fixtures/digest_items.json").read_text(encoding="utf-8"))
    out = write(
        render("תצוגה מקדימה מקבצי דוגמה.", items, for_date="preview"),
        "web/out",
        "preview",
    )
    print(f"Wrote {out} — open it in a browser.")


if __name__ == "__main__":
    if "--from-fixtures" in sys.argv:
        _preview()
