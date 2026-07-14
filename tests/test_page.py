import json
from pathlib import Path

from app.digest import page


def _items():
    return json.loads(Path("tests/fixtures/digest_items.json").read_text(encoding="utf-8"))


def test_render_is_rtl_hebrew_html():
    html = page.render("הבוקר היה שקט", _items(), for_date="2026-07-14")

    assert 'dir="rtl"' in html
    assert 'lang="he"' in html
    assert "הבוקר היה שקט" in html
    assert "2026-07-14" in html


def test_render_includes_each_video():
    html = page.render("body", _items(), for_date="2026-07-14")

    assert "https://www.instagram.com/reel/DY2QmhAoF-z/" in html
    assert "הילד רץ אחרי המשאית" in html
    assert "andrejko.epta" in html


def test_render_escapes_untrusted_captions():
    items = _items()
    items[0]["creator"] = "<script>alert(1)</script>"

    html = page.render("body", items, for_date="2026-07-14")

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_write_creates_dated_file(tmp_path):
    html = page.render("body", _items(), for_date="2026-07-14")

    path = page.write(html, str(tmp_path), "2026-07-14")

    assert path.endswith("2026-07-14.html")
    assert "body" in Path(path).read_text(encoding="utf-8")
