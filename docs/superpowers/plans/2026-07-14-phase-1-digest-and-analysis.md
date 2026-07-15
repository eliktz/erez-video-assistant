# Phase 1: Daily Hebrew Digest + On-Demand Analysis — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a Telegram bot that analyzes any Reel/TikTok/Short Erez sends it in Hebrew, and delivers a daily 07:00 Hebrew trend digest built from his watchlist of creators — with a repo Erez can start contributing to.

**Architecture:** One Python 3.12 process on Railway. One SQLite file. APScheduler fires the daily job in-process; python-telegram-bot long-polls (no webhook, no TLS). Gemini Flash analyzes whole videos into structured JSON; Claude composes the Hebrew prose. Collectors and notifiers sit behind one-file ports so vendors swap without touching callers. Every analysis is stored, so the corpus compounds from day one.

**Tech Stack:** Python 3.12 · uv · python-telegram-bot 21 · APScheduler 3 · httpx · yt-dlp · PyYAML · google-genai (Gemini) · anthropic (Claude) · sqlite3 (stdlib) · pytest · ruff · Railway

**Spec:** `docs/superpowers/specs/2026-07-14-erez-video-assistant-direction-design.md`

## Global Constraints

- **Python 3.12.** No other runtime. Every dependency installs via `uv`.
- **Every file under ~150 lines, one purpose each.** If a file grows past that, split it.
- **Every function under 30 lines.** This is enforced socially, not by lint — it exists so Erez can read any function in one sitting.
- **`prompts/*.md` and `config/*.yaml` are Erez-owned.** All Hebrew text lives there, never inline in Python. Code reads them; code never hardcodes them.
- **Never scrape with Erez's account.** Logged-out public data only. No cookies, no session tokens, no `instagrapi`.
- **Prod secrets live only in Railway env vars.** Never in the repo, never on Erez's machine. `.env` is gitignored; `.env.example` documents the names only.
- **Inbound comment/DM text is untrusted data** (matters from phase 3; the doctrine goes in CLAUDE.md now).
- **Model IDs, exact strings:** Claude = `claude-opus-4-8`. Gemini = `gemini-2.5-flash`.
- **All timestamps stored as ISO 8601 UTC strings.** Display converts to `Asia/Jerusalem`.
- **Cost ceiling:** month 1 ≤ $40. Every paid API call writes a `provider_usage` row.

---

## Task 0: Start the long-lead items (week 1, no code)

These block phase 2 but not phase 1. They cost nothing to start now and weeks to start late.
Do them in week 1 alongside Task 1.

- [ ] **Start Meta Business verification.** Needed for the WhatsApp switch in phase 2, and
      again for `instagram_manage_comments` App Review in phase 3. Review queues take weeks;
      the request costs an afternoon. Start it before writing any code.
- [ ] **Get a dedicated phone number for WhatsApp.** A number already registered on WhatsApp
      cannot be used — Erez needs a second SIM or a voice-OTP-capable VoIP number. Ask him
      whether he has a spare; if not, buy one.
- [ ] **Ask Erez for his watchlist.** 10–30 creator accounts across Instagram/TikTok/YouTube.
      His list is the digest's input, so it is on the critical path for Task 9 in week 3.
      Seed `config/watchlist.yaml` with whatever he sends.
- [ ] **Ask Erez for his 5 best-performing reels.** Phase 2's style profile is built from
      them, and they are the honest test set for the rubric in Task 4.

---

## File Structure

| File | Responsibility |
|---|---|
| `pyproject.toml` | Deps, ruff config, pytest config |
| `Makefile` | `setup`, `test`, `lint`, `run`, `digest-preview` |
| `CLAUDE.md` | Rules for AI pairing — bilingual, written for Erez |
| `.env.example` | Names of required env vars (no values) |
| `.github/workflows/ci.yml` | ruff + pytest + gitleaks on every PR |
| `config/watchlist.yaml` | **Erez owns.** Creators + topics to track |
| `config/settings.yaml` | Schedule, digest size, cost caps |
| `prompts/analysis_rubric.md` | **Erez owns.** What Gemini looks for in a video |
| `prompts/digest.md` | **Erez owns.** How Claude writes the daily digest |
| `prompts/bot_persona.md` | **Erez owns.** The bot's Hebrew voice |
| `app/config.py` | Load YAML + env into typed settings |
| `app/store/db.py` | Schema + connection |
| `app/store/videos.py` | Video + analysis read/write |
| `app/store/usage.py` | `provider_usage` write + monthly rollup |
| `app/collect/base.py` | `Source` port + `Candidate` dataclass |
| `app/collect/youtube.py` | YouTube Data API collector (free, official) |
| `app/collect/scraper.py` | Third-party scraper collector (IG + TikTok) |
| `app/analyze/fetch.py` | Get video bytes: yt-dlp or Telegram upload |
| `app/analyze/gemini.py` | Video → structured analysis JSON |
| `app/digest/rank.py` | Velocity score + top-N selection |
| `app/digest/compose.py` | Analyses → Hebrew digest via Claude |
| `app/digest/page.py` | Digest → static HTML page |
| `app/notify/base.py` | `Notifier` port |
| `app/notify/telegram.py` | Telegram implementation |
| `app/bot.py` | Command + message handlers |
| `app/jobs.py` | Daily digest job + dead-man's-switch |
| `app/main.py` | Entrypoint: wire bot + scheduler |
| `tests/fixtures/` | Cached JSON so tests need zero API keys |
| `docs/learn/` | Numbered 5-minute Hebrew lessons |

---

### Task 1: Repo skeleton, tooling, and CLAUDE.md

**Files:**
- Create: `pyproject.toml`, `Makefile`, `.env.example`, `.gitignore`, `.github/workflows/ci.yml`, `CLAUDE.md`, `app/__init__.py`, `tests/__init__.py`, `tests/test_smoke.py`

**Interfaces:**
- Consumes: nothing
- Produces: `make setup` / `make test` / `make lint` work; CI green on PRs

- [ ] **Step 1: Write the failing test**

Create `tests/test_smoke.py`:

```python
def test_app_package_imports():
    import app

    assert app.__name__ == "app"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_smoke.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app'`

- [ ] **Step 3: Create the package and config files**

Create `app/__init__.py` (empty file) and `tests/__init__.py` (empty file).

Create `pyproject.toml`:

```toml
[project]
name = "erez-video-assistant"
version = "0.1.0"
description = "AI assistant for Erez: viral trend digest + video analysis, in Hebrew"
requires-python = ">=3.12"
dependencies = [
    "python-telegram-bot>=21.0,<22",
    "apscheduler>=3.10,<4",
    "httpx>=0.27",
    "yt-dlp>=2025.1.1",
    "pyyaml>=6.0",
    "google-genai>=1.0",
    "anthropic>=0.40",
]

[dependency-groups]
dev = ["pytest>=8.0", "pytest-asyncio>=0.23", "ruff>=0.6"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
asyncio_mode = "auto"
```

`pythonpath = ["."]` is what makes `import app` work in tests without a build system —
one line instead of packaging ceremony a beginner would have to learn.

Create `Makefile` (tabs, not spaces, for recipe lines):

```makefile
.PHONY: setup test lint fix run digest-preview

setup:
	uv sync
	@echo "Ready. Copy .env.example to .env and fill it in."

test:
	uv run pytest -q

lint:
	uv run ruff check .

fix:
	uv run ruff check --fix .
	uv run ruff format .

run:
	uv run python -m app.main

digest-preview:
	uv run python -m app.digest.page --from-fixtures
```

Create `.gitignore`:

```
.env
.venv/
__pycache__/
*.pyc
data/
web/out/
.pytest_cache/
```

Create `.env.example`:

```
# Telegram — from @BotFather
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID_EREZ=
TELEGRAM_CHAT_ID_ADMIN=

# Gemini — https://aistudio.google.com/apikey
GEMINI_API_KEY=

# Claude — https://console.anthropic.com
ANTHROPIC_API_KEY=

# YouTube Data API — https://console.cloud.google.com
YOUTUBE_API_KEY=

# Scraper vendor (decided by the week-1 spike; leave blank until then)
SCRAPER_API_KEY=

# Where the SQLite file lives
DB_PATH=data/erez.db
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv sync && uv run pytest tests/test_smoke.py -v`
Expected: PASS

- [ ] **Step 5: Write CLAUDE.md**

Create `CLAUDE.md`:

````markdown
# CLAUDE.md

Guidance for Claude Code working in this repository.

## What this is

An AI assistant for Erez (@erez.v1), an Israeli creator of viral feel-good street videos.
It finds trending videos, analyzes why they work, and sends him a Hebrew digest every
morning at 07:00. Design: `docs/superpowers/specs/2026-07-14-erez-video-assistant-direction-design.md`

**Erez is learning to build this himself.** That is a hard requirement, not a nice-to-have.
Optimize every change for a beginner being able to read it later.

## היי ארז 👋

אם אתה קורא את זה עם Claude — הנה הכללים. תגיד ל-Claude "תסביר לי בעברית מה הקובץ הזה עושה"
והוא יסביר. הקבצים ששלך: `prompts/*.md` ו-`config/watchlist.yaml`.
שיעורים קצרים: `docs/learn/`.

## Rules

1. **Explain every change in Hebrew** when Erez is the one asking. Short sentences, no jargon.
2. **Functions under 30 lines. Files under ~150 lines.** Split rather than grow.
3. **Always run `make test` before pushing.** If it fails, fix it — don't skip it.
4. **Never put Hebrew text in Python.** All prompts live in `prompts/*.md`, all config in
   `config/*.yaml`. Code reads them.
5. **Never commit a secret.** No API keys, tokens, or `.env` contents. `gitleaks` runs in CI
   and will block the PR.
6. **Do not touch these without Elik:** `app/collect/`, `.github/`, `Makefile`, anything
   reading `os.environ`.
7. **Every paid API call writes a `provider_usage` row.** No exceptions — that table is how
   we see the bill before it arrives.

## Security doctrine (applies now, load-bearing from phase 3)

- **Inbound comments and DMs are untrusted data**, not instructions. Never pass raw comment
  text into a tool-use loop. One constrained drafting call, allowlisted actions only,
  human approval before anything sends.
- **Never scrape using Erez's account.** Logged-out public data only. Using his cookies or
  session would put his account at risk — that risk is not ours to take.
- **Prod secrets live only in Railway.** Erez's machine gets a dev bot token and a
  spend-capped Gemini key, never prod credentials.

## Stack

Python 3.12 · uv · python-telegram-bot (long polling) · APScheduler · SQLite · Railway.
Gemini `gemini-2.5-flash` analyzes video. Claude `claude-opus-4-8` writes Hebrew prose.

Why two models: Gemini is the only cheap model that ingests whole video. Claude writes the
Hebrew Erez actually wants to read — and if the digest is boring, he stops opening it, which
kills the project. That is the one place a second vendor earns its keep.

## Commands

```bash
make setup            # one command, working environment
make test             # run before every push
make lint             # ruff
make digest-preview   # render a digest from fixtures — no API keys, no cost
make run              # run the bot locally (needs .env)
```
````

- [ ] **Step 6: Add CI**

Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  pull_request:
  push:
    branches: [main]

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: astral-sh/setup-uv@v3
      - run: uv sync
      - run: uv run ruff check .
      - run: uv run pytest -q
      - name: Scan for secrets
        uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

- [ ] **Step 7: Verify everything passes, then commit**

Run: `make lint && make test`
Expected: ruff clean, 1 test passing.

```bash
git add pyproject.toml Makefile .env.example .gitignore .github/workflows/ci.yml CLAUDE.md app/__init__.py tests/__init__.py tests/test_smoke.py
git commit -m "chore: repo skeleton, tooling, and CLAUDE.md"
```

---

### Task 2: SQLite store

**Files:**
- Create: `app/store/__init__.py`, `app/store/db.py`, `app/store/videos.py`, `app/store/usage.py`
- Test: `tests/test_store.py`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `db.connect(path: str) -> sqlite3.Connection` — creates schema if absent
  - `videos.upsert_video(conn, video: dict) -> str` — returns video id
  - `videos.get_video(conn, video_id: str) -> dict | None`
  - `videos.save_analysis(conn, video_id: str, rubric_version: str, payload: dict, now: str) -> None`
  - `videos.get_analysis(conn, video_id: str, rubric_version: str) -> dict | None`
  - `usage.record(conn, provider: str, operation: str, units: float, cost_usd: float, now: str) -> None`
  - `usage.month_to_date(conn, month: str) -> list[dict]` — rows of `{provider, cost_usd, calls}`

- [ ] **Step 1: Write the failing test**

Create `tests/test_store.py`:

```python
from app.store import db, usage, videos

NOW = "2026-07-14T04:00:00Z"


def _conn():
    return db.connect(":memory:")


def test_upsert_video_is_idempotent():
    conn = _conn()
    row = {
        "id": "youtube:abc123",
        "platform": "youtube",
        "native_id": "abc123",
        "url": "https://youtube.com/shorts/abc123",
        "creator": "someone",
        "caption": "hello",
        "posted_at": "2026-07-13T10:00:00Z",
        "views": 1000,
        "likes": 50,
        "comments": 5,
        "source": "youtube",
    }
    videos.upsert_video(conn, row, now=NOW)
    row["views"] = 2000
    videos.upsert_video(conn, row, now=NOW)

    stored = videos.get_video(conn, "youtube:abc123")
    assert stored["views"] == 2000
    assert stored["first_seen_at"] == NOW


def test_save_and_get_analysis():
    conn = _conn()
    videos.upsert_video(
        conn,
        {
            "id": "youtube:abc123",
            "platform": "youtube",
            "native_id": "abc123",
            "url": "https://youtube.com/shorts/abc123",
            "creator": None,
            "caption": None,
            "posted_at": None,
            "views": 0,
            "likes": 0,
            "comments": 0,
            "source": "youtube",
        },
        now=NOW,
    )
    videos.save_analysis(conn, "youtube:abc123", "v1", {"hook": "כלב"}, now=NOW)

    got = videos.get_analysis(conn, "youtube:abc123", "v1")
    assert got["hook"] == "כלב"
    assert videos.get_analysis(conn, "youtube:abc123", "v2") is None


def test_usage_month_to_date_sums_by_provider():
    conn = _conn()
    usage.record(conn, "gemini", "analyze", 1, 0.01, now="2026-07-01T00:00:00Z")
    usage.record(conn, "gemini", "analyze", 1, 0.02, now="2026-07-02T00:00:00Z")
    usage.record(conn, "claude", "compose", 1, 0.10, now="2026-07-02T00:00:00Z")
    usage.record(conn, "gemini", "analyze", 1, 99.0, now="2026-06-30T00:00:00Z")

    rows = {r["provider"]: r for r in usage.month_to_date(conn, "2026-07")}
    assert rows["gemini"]["cost_usd"] == 0.03
    assert rows["gemini"]["calls"] == 2
    assert rows["claude"]["cost_usd"] == 0.10
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.store'`

- [ ] **Step 3: Implement the store**

Create `app/store/__init__.py` (empty).

Create `app/store/db.py`:

```python
"""SQLite connection and schema. One file, no server, inspectable with `sqlite3 data/erez.db`."""

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS videos (
    id            TEXT PRIMARY KEY,
    platform      TEXT NOT NULL,
    native_id     TEXT NOT NULL,
    url           TEXT NOT NULL,
    creator       TEXT,
    caption       TEXT,
    posted_at     TEXT,
    views         INTEGER,
    likes         INTEGER,
    comments      INTEGER,
    source        TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS analyses (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id       TEXT NOT NULL REFERENCES videos(id),
    rubric_version TEXT NOT NULL,
    payload_json   TEXT NOT NULL,
    created_at     TEXT NOT NULL,
    UNIQUE(video_id, rubric_version)
);

CREATE TABLE IF NOT EXISTS digests (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    for_date   TEXT NOT NULL UNIQUE,
    body_he    TEXT,
    html_path  TEXT,
    sent_at    TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS provider_usage (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    provider   TEXT NOT NULL,
    operation  TEXT NOT NULL,
    units      REAL NOT NULL,
    cost_usd   REAL NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_videos_posted ON videos(posted_at);
CREATE INDEX IF NOT EXISTS idx_usage_created ON provider_usage(created_at);
"""


def connect(path: str) -> sqlite3.Connection:
    """Open the database, creating the file and schema if needed."""
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.commit()
    return conn
```

Create `app/store/videos.py`:

```python
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
    row = conn.execute(
        f"SELECT {_FIELDS} FROM videos WHERE id = ?", (video_id,)
    ).fetchone()
    return dict(row) if row else None


def known_ids(conn: sqlite3.Connection, ids: list[str]) -> set[str]:
    """Which of these video ids do we already have? Used to skip re-analysis."""
    if not ids:
        return set()
    placeholders = ",".join("?" * len(ids))
    rows = conn.execute(
        f"SELECT id FROM videos WHERE id IN ({placeholders})", ids
    ).fetchall()
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


def get_analysis(
    conn: sqlite3.Connection, video_id: str, rubric_version: str
) -> dict | None:
    row = conn.execute(
        "SELECT payload_json FROM analyses WHERE video_id = ? AND rubric_version = ?",
        (video_id, rubric_version),
    ).fetchone()
    return json.loads(row["payload_json"]) if row else None
```

Create `app/store/usage.py`:

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_store.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add app/store tests/test_store.py
git commit -m "feat: SQLite store for videos, analyses, and provider usage"
```

---

### Task 3: Config loading

**Files:**
- Create: `app/config.py`, `config/watchlist.yaml`, `config/settings.yaml`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `config.load_watchlist(path: str = "config/watchlist.yaml") -> Watchlist` with `.creators: list[Creator]`, `.topics: list[str]` where `Creator` has `.platform`, `.handle`
  - `config.load_settings(path: str = "config/settings.yaml") -> dict`
  - `config.load_prompt(name: str) -> str` — reads `prompts/{name}.md`
  - `config.env(key: str, default: str | None = None) -> str` — raises `RuntimeError` if missing and no default

- [ ] **Step 1: Write the failing test**

Create `tests/test_config.py`:

```python
import pytest

from app import config


def test_load_watchlist_parses_creators(tmp_path):
    p = tmp_path / "watchlist.yaml"
    p.write_text(
        "creators:\n"
        "  - platform: instagram\n"
        "    handle: andrejko.epta\n"
        "  - platform: youtube\n"
        "    handle: UCxyz\n"
        "topics:\n"
        "  - random acts of kindness\n",
        encoding="utf-8",
    )
    wl = config.load_watchlist(str(p))

    assert len(wl.creators) == 2
    assert wl.creators[0].platform == "instagram"
    assert wl.creators[0].handle == "andrejko.epta"
    assert wl.topics == ["random acts of kindness"]


def test_load_watchlist_rejects_unknown_platform(tmp_path):
    p = tmp_path / "watchlist.yaml"
    p.write_text("creators:\n  - platform: myspace\n    handle: x\n", encoding="utf-8")

    with pytest.raises(ValueError, match="myspace"):
        config.load_watchlist(str(p))


def test_env_raises_when_missing(monkeypatch):
    monkeypatch.delenv("DEFINITELY_NOT_SET", raising=False)
    with pytest.raises(RuntimeError, match="DEFINITELY_NOT_SET"):
        config.env("DEFINITELY_NOT_SET")


def test_env_returns_default(monkeypatch):
    monkeypatch.delenv("DEFINITELY_NOT_SET", raising=False)
    assert config.env("DEFINITELY_NOT_SET", "fallback") == "fallback"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.config'`

- [ ] **Step 3: Implement config**

Create `app/config.py`:

```python
"""Load Erez-owned YAML and prompts, plus env vars. Fails loudly on bad input."""

import os
from dataclasses import dataclass
from pathlib import Path

import yaml

PLATFORMS = {"instagram", "tiktok", "youtube"}


@dataclass(frozen=True)
class Creator:
    platform: str
    handle: str


@dataclass(frozen=True)
class Watchlist:
    creators: list[Creator]
    topics: list[str]


def load_watchlist(path: str = "config/watchlist.yaml") -> Watchlist:
    """Read Erez's creator list. A typo here should fail now, not at 07:00."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    creators = []
    for entry in data.get("creators") or []:
        platform = str(entry["platform"]).lower()
        if platform not in PLATFORMS:
            raise ValueError(
                f"Unknown platform {platform!r} in {path}. Use one of: {sorted(PLATFORMS)}"
            )
        creators.append(Creator(platform=platform, handle=str(entry["handle"])))
    topics = [str(t) for t in (data.get("topics") or [])]
    return Watchlist(creators=creators, topics=topics)


def load_settings(path: str = "config/settings.yaml") -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}


def load_prompt(name: str) -> str:
    """Read prompts/{name}.md. All Hebrew lives there — never inline in code."""
    return Path(f"prompts/{name}.md").read_text(encoding="utf-8")


def env(key: str, default: str | None = None) -> str:
    value = os.environ.get(key, default)
    if value is None:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return value
```

Create `config/watchlist.yaml`:

```yaml
# הרשימה של ארז — מי לעקוב אחריו ומה לחפש.
# זה הקובץ שלך. תוסיף, תוריד, תשנה — הדוח של מחר ישתנה בהתאם.
#
# platform: instagram | tiktok | youtube
# handle: השם בכתובת של הפרופיל (בלי @)

creators:
  - platform: instagram
    handle: andrejko.epta

topics:
  - random acts of kindness
  - surprise gift stranger
```

Create `config/settings.yaml`:

```yaml
# הגדרות מערכת. אם משהו פה לא ברור — תשאל את אליק.

digest:
  hour: 7 # שעה בבוקר (שעון ישראל)
  minute: 0
  max_videos: 10 # כמה סרטונים לנתח בכל בוקר
  deadman_minute: 30 # אם לא יצא דוח עד 07:30 — תתריע לאליק

collect:
  lookback_hours: 48 # כמה אחורה לחפש סרטונים חדשים
  max_per_creator: 5

cost:
  monthly_cap_usd: 40 # החודש הראשון
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_config.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add app/config.py config/ tests/test_config.py
git commit -m "feat: config loading for watchlist, settings, and prompts"
```

---

### Task 4: Gemini video analysis (spike + implementation)

**Files:**
- Create: `app/analyze/__init__.py`, `app/analyze/gemini.py`, `prompts/analysis_rubric.md`, `tests/fixtures/analysis_sample.json`
- Test: `tests/test_gemini.py`

**Interfaces:**
- Consumes: `config.load_prompt`, `store.usage.record`
- Produces:
  - `gemini.RUBRIC_VERSION: str` — bump when the rubric changes materially
  - `gemini.analyze_video(video_path: str, rubric: str, client) -> dict` — parsed analysis. Params are positional-or-keyword on purpose: `bot.Deps.analyze` calls this positionally, tests call it by keyword.
  - `gemini.estimate_cost(seconds: float) -> float`
  - `gemini.build_client(api_key: str)`

**Note on the SDK:** Step 1 is a live spike because `google-genai` call shapes must be
confirmed against the installed version, not recalled. Do the spike first; if the shape
differs from Step 3's code, follow the spike and fix the code.

- [ ] **Step 1: Spike the Gemini SDK against a real video**

Download one short public video and confirm the call shape:

```bash
uv run yt-dlp -f "mp4[height<=720]" -o /tmp/spike.mp4 "https://www.youtube.com/watch?v=jNQXAC9IVRw"
```

```bash
uv run python -c "
from google import genai
import os
client = genai.Client(api_key=os.environ['GEMINI_API_KEY'])
f = client.files.upload(file='/tmp/spike.mp4')
r = client.models.generate_content(model='gemini-2.5-flash', contents=[f, 'Describe this video in one sentence, in Hebrew.'])
print(r.text)
print(r.usage_metadata)
"
```

Expected: a Hebrew sentence, plus a usage object with a `prompt_token_count`.
**Record the exact attribute names you see** — Step 3 depends on them.

- [ ] **Step 2: Write the failing test**

Create `tests/fixtures/analysis_sample.json`:

```json
{
  "hook": "הילד רץ אחרי המשאית",
  "hook_seconds": 1.5,
  "format": "street candid",
  "why_it_worked": "רגע אמיתי בלי בימוי, פנים של הילד ממלאות את הפריים",
  "emotional_arc": "מתח -> הפתעה -> חיוך",
  "audio": "מוזיקה עולה בשנייה 3",
  "transferable_idea": "לצלם את הרגע לפני ההפתעה, לא רק את ההפתעה",
  "fits_erez_style": true
}
```

Create `tests/test_gemini.py`:

````python
import json
from pathlib import Path

from app.analyze import gemini


class _FakeResponse:
    def __init__(self, text):
        self.text = text
        self.usage_metadata = None


class _FakeModels:
    def __init__(self, text):
        self._text = text
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeResponse(self._text)


class _FakeFiles:
    def upload(self, file):
        return {"uri": f"fake://{file}"}


class _FakeClient:
    def __init__(self, text):
        self.files = _FakeFiles()
        self.models = _FakeModels(text)


def test_analyze_video_parses_json_response():
    sample = Path("tests/fixtures/analysis_sample.json").read_text(encoding="utf-8")
    client = _FakeClient(sample)

    result = gemini.analyze_video(
        "/tmp/x.mp4", rubric="rubric text", client=client
    )

    assert result["hook"] == "הילד רץ אחרי המשאית"
    assert result["fits_erez_style"] is True
    assert client.models.calls[0]["model"] == "gemini-2.5-flash"


def test_analyze_video_strips_markdown_fences():
    sample = json.dumps({"hook": "x"}, ensure_ascii=False)
    client = _FakeClient(f"```json\n{sample}\n```")

    result = gemini.analyze_video("/tmp/x.mp4", rubric="r", client=client)

    assert result["hook"] == "x"


def test_estimate_cost_is_cents_per_video():
    # A 60s video is roughly 15,780 input tokens at $0.30/1M.
    cost = gemini.estimate_cost(60)
    assert 0.001 < cost < 0.05
````

- [ ] **Step 3: Run it to verify it fails**

Run: `uv run pytest tests/test_gemini.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.analyze'`

- [ ] **Step 4: Implement the analyzer**

Create `app/analyze/__init__.py` (empty).

Create `app/analyze/gemini.py`:

````python
"""Send a whole video to Gemini and get back structured analysis.

Gemini is the only cheap model that ingests video directly, and it handles Hebrew.
Roughly half a cent per 60-second video.
"""

import json

MODEL = "gemini-2.5-flash"
RUBRIC_VERSION = "v1"

# Verified 2026-07-13: $0.30 per 1M input tokens on gemini-2.5-flash.
# Video tokenizes at roughly 100-300 tokens/sec depending on resolution; 263 is
# mid-range. Treat the result as order-of-magnitude, not an invoice.
_USD_PER_INPUT_TOKEN = 0.30 / 1_000_000
_TOKENS_PER_SECOND = 263


def estimate_cost(seconds: float) -> float:
    """Rough input cost for analyzing a video of this length."""
    return seconds * _TOKENS_PER_SECOND * _USD_PER_INPUT_TOKEN


def _strip_fences(text: str) -> str:
    """Models sometimes wrap JSON in ```json fences. Take the JSON either way."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
        cleaned = cleaned.rsplit("```", 1)[0]
    return cleaned.strip()


def analyze_video(video_path: str, rubric: str, client) -> dict:
    """Analyze one video against the rubric. Returns the parsed JSON payload.

    `client` is a google.genai Client (injected so tests need no API key).
    Positional-or-keyword by design: callers inject a stand-in with the same shape.
    """
    uploaded = client.files.upload(file=video_path)
    response = client.models.generate_content(
        model=MODEL,
        contents=[uploaded, rubric],
    )
    return json.loads(_strip_fences(response.text))


def build_client(api_key: str):
    """Real client. Kept separate so every other function stays testable."""
    from google import genai

    return genai.Client(api_key=api_key)
````

Create `prompts/analysis_rubric.md`:

````markdown
# ניתוח סרטון — מה לחפש

ארז: זה הקובץ שאומר ל-AI מה לחפש בכל סרטון. תשנה אותו כמו שאתה רוצה —
תוסיף שאלות, תוריד שאלות. מחר הניתוח יראה אחרת.

---

אתה מנתח סרטונים ויראליים קצרים בשביל יוצר תוכן ישראלי.
עולם התוכן שלו: רגעים אמיתיים ברחוב, מעשים טובים בלי שמישהו שם לב, אנשים אמיתיים, בלי בימוי.

תנתח את הסרטון המצורף ותחזיר **רק JSON**, בלי טקסט לפני או אחרי, לפי המבנה הזה:

```json
{
  "hook": "מה קורה ב-3 השניות הראשונות שגורם לא לגלול הלאה",
  "hook_seconds": 0.0,
  "format": "סוג הסרטון בכמה מילים",
  "why_it_worked": "למה זה עבד. תהיה ספציפי — לא 'זה מרגש' אלא מה בדיוק גרם לזה",
  "emotional_arc": "המסע הרגשי בחצים, למשל: סקרנות -> מתח -> הקלה",
  "audio": "מה קורה בפס הקול ומתי",
  "transferable_idea": "רעיון קונקרטי שארז יכול לקחת מזה לעולם התוכן שלו",
  "fits_erez_style": true
}
```

כללים:
- כל הטקסט בעברית.
- `fits_erez_style` — true רק אם זה באמת מתחבר לרגעים אמיתיים ברחוב. אל תגיד true סתם.
- אם אתה לא בטוח במשהו, תגיד את זה בשדה עצמו. אל תמציא.
````

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_gemini.py -v`
Expected: 3 passed

- [ ] **Step 6: Verify against the real API**

Run:

```bash
uv run python -c "
from app.analyze import gemini
from app import config
c = gemini.build_client(config.env('GEMINI_API_KEY'))
r = gemini.analyze_video('/tmp/spike.mp4', rubric=config.load_prompt('analysis_rubric'), client=c)
import json; print(json.dumps(r, ensure_ascii=False, indent=2))
"
```

Expected: valid JSON with Hebrew values in every field.
**This is the riskiest assumption in the whole project. If the Hebrew is weak or the
analysis is generic, stop and tune `prompts/analysis_rubric.md` before building anything else.**

- [ ] **Step 7: Commit**

```bash
git add app/analyze prompts/analysis_rubric.md tests/test_gemini.py tests/fixtures/analysis_sample.json
git commit -m "feat: Gemini video analysis with Hebrew rubric"
```

---

### Task 5: Video fetching

**Files:**
- Create: `app/analyze/fetch.py`
- Test: `tests/test_fetch.py`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `fetch.download(url: str, dest_dir: str, *, runner=None) -> FetchResult` where `FetchResult` has `.path: str`, `.duration_seconds: float`
  - `fetch.FetchError` — raised when download fails
  - `fetch.TELEGRAM_MAX_BYTES: int` — 20MB, the Telegram getFile ceiling

- [ ] **Step 1: Write the failing test**

Create `tests/test_fetch.py`:

```python
import pytest

from app.analyze import fetch


def test_download_builds_expected_ytdlp_options():
    captured = {}

    def fake_runner(url, opts):
        captured["url"] = url
        captured["opts"] = opts
        return {"duration": 42.0, "_filename": "/tmp/out/vid.mp4"}

    result = fetch.download(
        "https://tiktok.com/@x/video/1", "/tmp/out", runner=fake_runner
    )

    assert result.path == "/tmp/out/vid.mp4"
    assert result.duration_seconds == 42.0
    assert captured["url"] == "https://tiktok.com/@x/video/1"
    # Logged-out only: never send cookies, never use Erez's account.
    assert "cookiefile" not in captured["opts"]
    assert captured["opts"]["noplaylist"] is True


def test_download_raises_fetch_error_on_failure():
    def failing_runner(url, opts):
        raise RuntimeError("HTTP 403")

    with pytest.raises(fetch.FetchError, match="403"):
        fetch.download("https://x.com/1", "/tmp/out", runner=failing_runner)


def test_download_rejects_missing_duration():
    def runner(url, opts):
        return {"_filename": "/tmp/out/vid.mp4"}

    with pytest.raises(fetch.FetchError, match="duration"):
        fetch.download("https://x.com/1", "/tmp/out", runner=runner)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_fetch.py -v`
Expected: FAIL — `ImportError: cannot import name 'fetch'`

- [ ] **Step 3: Implement fetch**

Create `app/analyze/fetch.py`:

```python
"""Get video bytes for analysis.

Two paths: yt-dlp for a public URL, or the file Telegram already has when Erez
uploads directly. The upload path needs no scraping at all, which is why it is
the fallback when yt-dlp gets blocked.
"""

from dataclasses import dataclass

# Telegram's getFile refuses anything larger. A 60s 1080p reel can exceed this,
# so the URL path stays primary and this is the fallback.
TELEGRAM_MAX_BYTES = 20 * 1024 * 1024


class FetchError(Exception):
    """Could not get the video. Message is safe to show a user."""


@dataclass(frozen=True)
class FetchResult:
    path: str
    duration_seconds: float


def _default_runner(url: str, opts: dict) -> dict:
    import yt_dlp

    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=True)


def download(url: str, dest_dir: str, *, runner=None) -> FetchResult:
    """Download a public video. Logged out, always — never Erez's account."""
    runner = runner or _default_runner
    opts = {
        "outtmpl": f"{dest_dir}/%(id)s.%(ext)s",
        "format": "mp4[height<=720]/best[height<=720]/best",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }
    try:
        info = runner(url, opts)
    except Exception as exc:  # yt-dlp raises many types; the caller only needs one
        raise FetchError(f"Could not download {url}: {exc}") from exc

    duration = info.get("duration")
    if duration is None:
        raise FetchError(f"No duration reported for {url}; refusing to guess cost.")
    return FetchResult(path=info["_filename"], duration_seconds=float(duration))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_fetch.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add app/analyze/fetch.py tests/test_fetch.py
git commit -m "feat: video fetching via yt-dlp, logged out only"
```

---

### Task 6: Hebrew composition via Claude

**Files:**
- Create: `app/digest/__init__.py`, `app/digest/compose.py`, `prompts/bot_persona.md`, `prompts/digest.md`
- Test: `tests/test_compose.py`

**Interfaces:**
- Consumes: `config.load_prompt`
- Produces:
  - `compose.MODEL: str` = `"claude-opus-4-8"`
  - `compose.reply_about_video(analysis: dict, persona: str, client) -> str` — Hebrew chat reply
  - `compose.write_digest(items: list[dict], template: str, client) -> str` — Hebrew digest body
  - `compose.build_client(api_key: str)`
  - `compose.estimate_cost(usage) -> float`

Both composers take positional-or-keyword params: `bot.Deps.compose_reply` and
`jobs.run_digest`'s `compose_digest` call them positionally; tests call them by keyword.

- [ ] **Step 1: Write the failing test**

Create `tests/test_compose.py`:

```python
from app.digest import compose


class _FakeUsage:
    input_tokens = 1000
    output_tokens = 500
    cache_read_input_tokens = 0
    cache_creation_input_tokens = 0


class _FakeBlock:
    type = "text"

    def __init__(self, text):
        self.text = text


class _FakeMessage:
    def __init__(self, text):
        self.content = [_FakeBlock(text)]
        self.usage = _FakeUsage()
        self.stop_reason = "end_turn"


class _FakeMessages:
    def __init__(self, text):
        self._text = text
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeMessage(self._text)


class _FakeClient:
    def __init__(self, text):
        self.messages = _FakeMessages(text)


def test_reply_about_video_returns_hebrew_text():
    client = _FakeClient("ההוק פה זה הרגע לפני ההפתעה.")

    out = compose.reply_about_video(
        {"hook": "x", "why_it_worked": "y"}, persona="תדבר בעברית", client=client
    )

    assert out == "ההוק פה זה הרגע לפני ההפתעה."
    call = client.messages.calls[0]
    assert call["model"] == "claude-opus-4-8"
    assert call["system"] == "תדבר בעברית"


def test_write_digest_includes_every_item():
    client = _FakeClient("הדוח של הבוקר")

    out = compose.write_digest(
        [{"hook": "a"}, {"hook": "b"}], template="כתוב דוח", client=client
    )

    assert out == "הדוח של הבוקר"
    prompt = client.messages.calls[0]["messages"][0]["content"]
    assert '"a"' in prompt and '"b"' in prompt


def test_estimate_cost_uses_opus_rates():
    # $5/1M in, $25/1M out -> 1000 in + 500 out = 0.005 + 0.0125
    assert abs(compose.estimate_cost(_FakeUsage()) - 0.0175) < 1e-6
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_compose.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.digest'`

- [ ] **Step 3: Implement compose**

Create `app/digest/__init__.py` (empty).

Create `app/digest/compose.py`:

```python
"""Turn structured analysis into Hebrew Erez wants to read.

Gemini understands the video; Claude writes the words. Both adversarial judges
flagged bland Hebrew prose as the single likeliest reason Erez stops opening the
digest — which would kill the project. That is why a second vendor is here.
"""

import json

MODEL = "claude-opus-4-8"

# Verified 2026-07-13: claude-opus-4-8 is $5/1M input, $25/1M output.
_USD_PER_INPUT_TOKEN = 5.0 / 1_000_000
_USD_PER_OUTPUT_TOKEN = 25.0 / 1_000_000


def estimate_cost(usage) -> float:
    """Cost of one Claude call from its usage object."""
    return (
        usage.input_tokens * _USD_PER_INPUT_TOKEN
        + usage.output_tokens * _USD_PER_OUTPUT_TOKEN
    )


def _text_of(message) -> str:
    """Pull the text out of a response. content is a list of typed blocks."""
    for block in message.content:
        if block.type == "text":
            return block.text
    return ""


def _ask(client, *, system: str, prompt: str, max_tokens: int):
    return client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        thinking={"type": "adaptive"},
        output_config={"effort": "medium"},
        messages=[{"role": "user", "content": prompt}],
    )


def reply_about_video(analysis: dict, persona: str, client) -> str:
    """One video's analysis -> a Hebrew chat reply in Erez's bot's voice."""
    prompt = (
        "הנה הניתוח הגולמי של הסרטון. תסביר לארז בעברית מה מעניין פה.\n\n"
        + json.dumps(analysis, ensure_ascii=False, indent=2)
    )
    return _text_of(_ask(client, system=persona, prompt=prompt, max_tokens=2000))


def write_digest(items: list[dict], template: str, client) -> str:
    """The morning digest: several analyses -> one Hebrew report."""
    prompt = (
        "הנה הסרטונים של הבוקר עם הניתוח של כל אחד.\n\n"
        + json.dumps(items, ensure_ascii=False, indent=2)
    )
    return _text_of(_ask(client, system=template, prompt=prompt, max_tokens=4000))


def build_client(api_key: str):
    import anthropic

    return anthropic.Anthropic(api_key=api_key)
```

Create `prompts/bot_persona.md`:

```markdown
# הקול של הבוט

ארז: ככה הבוט מדבר אליך. לא מוצא חן בעיניך? תשנה כאן.

---

אתה העוזר האישי של ארז, יוצר תוכן ישראלי.
עולם התוכן שלו: רגעים אמיתיים ברחוב, מעשים טובים בלי שמישהו שם לב.

איך אתה מדבר:
- עברית טבעית. כמו חבר שמבין בתוכן, לא כמו מדריך.
- ישר לעניין. המשפט הראשון הוא התשובה, לא הקדמה.
- ספציפי. "ההוק פה זה השנייה שהילד מבין מה קורה" ולא "הסרטון מרגש".
- כן. אם סרטון לא מיוחד — תגיד. אם משהו לא יעבוד לארז — תגיד.
- בלי אימוג'ים בכל שורה. אחד פה ושם זה בסדר.
- בלי בולטים אלא אם יש באמת רשימה.
```

Create `prompts/digest.md`:

```markdown
# הדוח היומי

ארז: זה מה שקובע איך נראה הדוח של הבוקר. תשנה סדר, תוסיף חלקים, תוריד חלקים.

---

אתה כותב את הדוח היומי של ארז, יוצר תוכן ישראלי.
עולם התוכן שלו: רגעים אמיתיים ברחוב, מעשים טובים בלי שמישהו שם לב.

תקבל רשימת סרטונים עם ניתוח של כל אחד. תכתוב דוח קצר בעברית, לקריאה של שתי דקות עם הקפה.

מבנה:
1. **שורה אחת בהתחלה** — מה הדבר הכי חשוב הבוקר. משפט אחד.
2. **הסרטונים** — לכל סרטון: מה קרה, למה זה עבד (ספציפי!), ומה ארז יכול לקחת מזה.
3. **רעיון אחד לארז** — הדבר הכי מעניין שראית היום, מתורגם לעולם התוכן שלו ולקהל הישראלי.

כללים:
- עברית טבעית. אתה כותב לחבר, לא מגיש דוח למנהל.
- ספציפי תמיד. "ההוק זה השנייה שהילד מבין" ולא "פתיחה חזקה".
- אם הבוקר משעמם — תגיד. עדיף דוח קצר וכן מדוח ארוך ומנופח.
- בלי "בעידן הדיגיטלי של היום". בלי מילים גדולות. בלי מילוי.
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_compose.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add app/digest prompts/bot_persona.md prompts/digest.md tests/test_compose.py
git commit -m "feat: Hebrew composition via Claude"
```

---

### Task 7: Telegram bot with /analyze — the first win

**Files:**
- Create: `app/notify/__init__.py`, `app/notify/base.py`, `app/notify/telegram.py`, `app/bot.py`, `app/main.py`
- Test: `tests/test_bot.py`

**Interfaces:**
- Consumes: `fetch.download`, `gemini.analyze_video`, `compose.reply_about_video`, `store.*`, `config.*`
- Produces:
  - `notify.base.Notifier` protocol with `send(text: str) -> None`
  - `notify.telegram.TelegramNotifier(token, chat_id, *, client=None)`
  - `bot.analyze_url(url, *, deps: Deps) -> str` — the whole pipeline, returns Hebrew text
  - `bot.video_id_from_url(url: str) -> str | None` — `"instagram:DY2QmhAoF-z"`
  - `bot.utc_now() -> str` — ISO 8601 UTC
  - `bot.URL_RE` — compiled URL matcher
  - `bot.Deps` dataclass: `conn`, `gemini_client`, `claude_client`, `rubric`, `persona`, `work_dir`, and the injectable seams `now`, `download`, `analyze`, `compose_reply` (each defaulting to the real implementation)
  - `main.build_deps() -> bot.Deps`, `main.main()` — entrypoint

- [ ] **Step 1: Write the failing test**

Create `tests/test_bot.py`:

```python
import json
from pathlib import Path

from app import bot
from app.analyze import fetch
from app.store import db, usage


def _deps(tmp_path, *, analysis=None, reply="ניתוח בעברית", fail=False):
    sample = analysis or json.loads(
        Path("tests/fixtures/analysis_sample.json").read_text(encoding="utf-8")
    )

    def fake_download(url, dest, runner=None):
        if fail:
            raise fetch.FetchError("HTTP 403 blocked")
        return fetch.FetchResult(path=str(tmp_path / "v.mp4"), duration_seconds=30.0)

    return bot.Deps(
        conn=db.connect(":memory:"),
        gemini_client=object(),
        claude_client=object(),
        rubric="rubric",
        persona="persona",
        work_dir=str(tmp_path),
        now=lambda: "2026-07-14T05:00:00Z",
        download=fake_download,
        analyze=lambda path, rubric, client: sample,
        compose_reply=lambda analysis, persona, client: reply,
    )


def test_analyze_url_returns_hebrew_and_stores_everything(tmp_path):
    deps = _deps(tmp_path)

    out = bot.analyze_url("https://www.instagram.com/reel/DY2QmhAoF-z/", deps=deps)

    assert out == "ניתוח בעברית"
    rows = deps.conn.execute("SELECT id, platform FROM videos").fetchall()
    assert rows[0]["platform"] == "instagram"
    assert deps.conn.execute("SELECT COUNT(*) c FROM analyses").fetchone()["c"] == 1
    spend = usage.month_to_date(deps.conn, "2026-07")
    assert spend[0]["provider"] == "gemini"


def test_analyze_url_reuses_stored_analysis(tmp_path):
    deps = _deps(tmp_path)
    url = "https://www.instagram.com/reel/DY2QmhAoF-z/"

    bot.analyze_url(url, deps=deps)
    bot.analyze_url(url, deps=deps)

    # Second call must not pay Gemini again.
    calls = deps.conn.execute(
        "SELECT COUNT(*) c FROM provider_usage WHERE provider='gemini'"
    ).fetchone()["c"]
    assert calls == 1


def test_analyze_url_returns_friendly_hebrew_on_download_failure(tmp_path):
    deps = _deps(tmp_path, fail=True)

    out = bot.analyze_url("https://x.com/1", deps=deps)

    assert "לא הצלחתי" in out


def test_video_id_from_url_is_stable():
    a = bot.video_id_from_url("https://www.instagram.com/reel/DY2QmhAoF-z/")
    b = bot.video_id_from_url("https://www.instagram.com/reel/DY2QmhAoF-z/?igsh=xyz")
    assert a == b == "instagram:DY2QmhAoF-z"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_bot.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.bot'`

- [ ] **Step 3: Implement the notifier port**

Create `app/notify/__init__.py` (empty).

Create `app/notify/base.py`:

```python
"""The interface layer sits behind this port.

Telegram now; WhatsApp when Meta's paperwork clears. Swapping one for the other
should touch this folder and nothing else.
"""

from typing import Protocol


class Notifier(Protocol):
    def send(self, text: str) -> None:
        """Deliver a message to its recipient. Raises on permanent failure."""
        ...
```

Create `app/notify/telegram.py`:

```python
"""Telegram delivery. Long polling: no webhook, no domain, no TLS cert."""

import httpx


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str, *, client: httpx.Client | None = None):
        self._url = f"https://api.telegram.org/bot{token}/sendMessage"
        self._chat_id = chat_id
        self._client = client or httpx.Client(timeout=30)

    def send(self, text: str) -> None:
        response = self._client.post(
            self._url,
            json={"chat_id": self._chat_id, "text": text, "parse_mode": "Markdown"},
        )
        response.raise_for_status()
```

- [ ] **Step 4: Implement the bot**

Create `app/bot.py`:

```python
"""The bot: Erez sends a link, gets Hebrew analysis back.

This ships before the digest on purpose. It needs no data vendor, and it proves
the one assumption everything else rests on: that the Hebrew analysis is good
enough that Erez wants more of it.
"""

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from app.analyze import fetch, gemini
from app.store import usage, videos

_URL_PATTERNS = [
    (re.compile(r"instagram\.com/(?:reel|p)/([A-Za-z0-9_-]+)"), "instagram"),
    (re.compile(r"tiktok\.com/.*?/video/(\d+)"), "tiktok"),
    (re.compile(r"(?:youtube\.com/shorts/|youtu\.be/)([A-Za-z0-9_-]+)"), "youtube"),
    (re.compile(r"youtube\.com/watch\?v=([A-Za-z0-9_-]+)"), "youtube"),
]

URL_RE = re.compile(r"https?://\S+")


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class Deps:
    """Everything the pipeline needs, injected so tests need no keys and no network."""

    conn: object
    gemini_client: object
    claude_client: object
    rubric: str
    persona: str
    work_dir: str
    now: Callable[[], str] = utc_now
    download: Callable = fetch.download
    analyze: Callable = None
    compose_reply: Callable = None


def video_id_from_url(url: str) -> str | None:
    """Stable id across tracking params: 'instagram:DY2QmhAoF-z'."""
    for pattern, platform in _URL_PATTERNS:
        match = pattern.search(url)
        if match:
            return f"{platform}:{match.group(1)}"
    return None


def _store_video(deps: Deps, video_id: str, url: str) -> None:
    platform, native_id = video_id.split(":", 1)
    videos.upsert_video(
        deps.conn,
        {
            "id": video_id,
            "platform": platform,
            "native_id": native_id,
            "url": url,
            "creator": None,
            "caption": None,
            "posted_at": None,
            "views": None,
            "likes": None,
            "comments": None,
            "source": "on_demand",
        },
        now=deps.now(),
    )


def analyze_url(url: str, *, deps: Deps) -> str:
    """The whole on-demand path. Returns Hebrew text safe to send to Erez."""
    video_id = video_id_from_url(url)
    if video_id is None:
        return "לא זיהיתי את הלינק. שלח לי לינק לרילס, טיקטוק או שורטס."

    _store_video(deps, video_id, url)

    analysis = videos.get_analysis(deps.conn, video_id, gemini.RUBRIC_VERSION)
    if analysis is None:
        try:
            result = deps.download(url, deps.work_dir)
        except fetch.FetchError:
            return "לא הצלחתי להוריד את הסרטון. נסה לשלוח לי את הקובץ עצמו."

        analyze = deps.analyze or gemini.analyze_video
        analysis = analyze(result.path, deps.rubric, deps.gemini_client)
        videos.save_analysis(
            deps.conn, video_id, gemini.RUBRIC_VERSION, analysis, now=deps.now()
        )
        usage.record(
            deps.conn,
            "gemini",
            "analyze_video",
            1,
            gemini.estimate_cost(result.duration_seconds),
            now=deps.now(),
        )

    from app.digest import compose

    compose_reply = deps.compose_reply or compose.reply_about_video
    return compose_reply(analysis, deps.persona, deps.claude_client)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_bot.py -v`
Expected: 4 passed

- [ ] **Step 6: Wire the entrypoint**

Create `app/main.py`:

```python
"""Entrypoint: one process, bot + scheduler. Run with `make run`."""

import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from app import bot, config
from app.analyze import gemini
from app.digest import compose
from app.store import db

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s %(message)s", level=logging.INFO
)
log = logging.getLogger(__name__)


def build_deps() -> bot.Deps:
    return bot.Deps(
        conn=db.connect(config.env("DB_PATH", "data/erez.db")),
        gemini_client=gemini.build_client(config.env("GEMINI_API_KEY")),
        claude_client=compose.build_client(config.env("ANTHROPIC_API_KEY")),
        rubric=config.load_prompt("analysis_rubric"),
        persona=config.load_prompt("bot_persona"),
        work_dir="/tmp/erez-videos",
    )


async def on_start(update: Update, _ctx) -> None:
    await update.message.reply_text(
        "היי ארז 👋\nשלח לי לינק לרילס/טיקטוק/שורטס ואני אנתח לך אותו.\n"
        "כל בוקר ב-7:00 תקבל ממני דוח טרנדים."
    )


async def on_message(update: Update, ctx) -> None:
    match = bot.URL_RE.search(update.message.text or "")
    if not match:
        await update.message.reply_text("שלח לי לינק לסרטון ואני אנתח אותו.")
        return
    await update.message.reply_text("רגע, מנתח... 🎬")
    reply = bot.analyze_url(match.group(0), deps=ctx.bot_data["deps"])
    await update.message.reply_text(reply)


def main() -> None:
    app = Application.builder().token(config.env("TELEGRAM_BOT_TOKEN")).build()
    app.bot_data["deps"] = build_deps()
    app.add_handler(CommandHandler("start", on_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    log.info("Bot starting (long polling)")
    app.run_polling()


if __name__ == "__main__":
    main()
```

- [ ] **Step 7: Verify end to end against real Telegram**

Create a bot with @BotFather, put the token in `.env`, then:

Run: `make run`
Then send the bot Erez's own best reel: `https://www.instagram.com/reel/DY2QmhAoF-z/`

Expected: within ~30 seconds, a Hebrew analysis naming a specific hook.
**This is the week-2 deliverable and the project's first real proof. If the Hebrew reads
like a translated press release, tune `prompts/bot_persona.md` until it doesn't.**

- [ ] **Step 8: Commit**

```bash
git add app/notify app/bot.py app/main.py tests/test_bot.py
git commit -m "feat: Telegram bot with on-demand Hebrew video analysis"
```

---

### Task 8: Deploy to Railway

**Files:**
- Create: `Procfile`, `railway.json`, `docs/learn/01-what-is-this.md`

**Interfaces:**
- Consumes: `app.main`
- Produces: bot running 24/7; push to `main` redeploys; one-click rollback

- [ ] **Step 1: Add the process definition**

Create `Procfile`:

```
worker: python -m app.main
```

Create `railway.json`:

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": { "builder": "NIXPACKS" },
  "deploy": {
    "startCommand": "python -m app.main",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

- [ ] **Step 2: Deploy**

```bash
railway login
railway init
railway up
```

Then in the Railway dashboard: add a volume mounted at `/data`, and set env vars
`DB_PATH=/data/erez.db` plus every key from `.env.example`.

- [ ] **Step 3: Verify the deployed bot answers**

Send the deployed bot a reel link from Telegram.
Expected: Hebrew analysis, same as local. Check `railway logs` for errors.

- [ ] **Step 4: Write Erez's first lesson**

Create `docs/learn/01-what-is-this.md`:

````markdown
# 1. מה זה הדבר הזה? (5 דקות)

## התמונה הגדולה

יש תוכנית אחת שרצה על שרת בענן, 24 שעות ביממה. היא עושה שני דברים:

1. **כשאתה שולח לה לינק** — היא מורידה את הסרטון, שולחת אותו ל-AI שרואה וידאו
   (Gemini), מקבלת ניתוח, ומבקשת מ-AI אחר (Claude) לכתוב לך את זה בעברית יפה.
2. **כל בוקר ב-7:00** — היא עושה את זה לבד על הסרטונים החדשים של היוצרים שברשימה שלך.

## איפה הדברים

| תיקייה | מה יש שם |
|---|---|
| `prompts/` | **שלך.** הטקסטים שאומרים ל-AI מה לעשות. עברית. |
| `config/` | **שלך.** רשימת היוצרים והגדרות. |
| `app/` | הקוד. נגיע לזה. |
| `tests/` | בדיקות שרצות אוטומטית ותופסות טעויות. |

## התרגיל הראשון שלך

1. תיכנס ל-`config/watchlist.yaml` בגיטהאב.
2. תלחץ על העיפרון (עריכה).
3. תוסיף יוצר שאתה אוהב:

```yaml
  - platform: instagram
    handle: השם_שלו
```

4. תלחץ "Commit changes", תבחר "Create a new branch", ותפתח Pull Request.
5. אליק יאשר. מחר בבוקר הדוח כבר יכלול אותו.

**זהו. שינית משהו שרץ בייצור, בלי שורת קוד אחת.**
````

- [ ] **Step 5: Commit**

```bash
git add Procfile railway.json docs/learn/01-what-is-this.md
git commit -m "chore: Railway deployment + Erez's first lesson"
```

---

### Task 9: Collectors — port, YouTube, and the vendor spike

**Files:**
- Create: `app/collect/__init__.py`, `app/collect/base.py`, `app/collect/youtube.py`, `app/collect/scraper.py`
- Test: `tests/test_collect.py`, `tests/fixtures/youtube_search.json`

**Interfaces:**
- Consumes: `config.Creator`, `config.Watchlist`
- Produces:
  - `base.Candidate` frozen dataclass: `id`, `platform`, `native_id`, `url`, `creator`, `caption`, `posted_at`, `views`, `likes`, `comments`, `source`; `.as_row() -> dict`
  - `base.Source` protocol: `.name: str`, `.collect(watchlist, *, since: str) -> list[Candidate]`
  - `youtube.YouTubeSource(api_key, *, http=None)` — free, official
  - `scraper.ScraperSource(api_key, *, http=None)` — IG + TikTok, vendor per spike

**Note:** `scraper.py` is the vendor seam. Swapping EnsembleData for Apify must touch
this file only.

- [ ] **Step 1: Run the vendor spike before writing code**

This decides a $49–100/month line item. Measure, don't assume.

```bash
# EnsembleData free trial: 50 units/day
curl -s "https://ensembledata.com/apis/instagram/user/posts?depth=1&user_id=<id>&token=$SCRAPER_API_KEY" | head -c 2000
```

Record for each candidate vendor: units consumed per creator fetched, fields returned
(does it include `play_count` and `taken_at`?), and whether TikTok and Instagram both work.

**Write the numbers into `docs/vendor-spike.md`. Decide the tier in week 4 from measured
units/day — not now.**

- [ ] **Step 2: Write the failing test**

Create `tests/fixtures/youtube_search.json`:

```json
{
  "items": [
    {
      "id": { "videoId": "abc123" },
      "snippet": {
        "publishedAt": "2026-07-13T10:00:00Z",
        "channelTitle": "Kindness Daily",
        "title": "He didn't know he was being filmed"
      }
    }
  ]
}
```

Create `tests/test_collect.py`:

```python
import json
from pathlib import Path

from app.collect import base, youtube
from app.config import Creator, Watchlist


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeHttp:
    def __init__(self, payload):
        self._payload = payload
        self.calls = []

    def get(self, url, params=None):
        self.calls.append({"url": url, "params": params})
        return _FakeResponse(self._payload)


def test_candidate_as_row_matches_store_schema():
    c = base.Candidate(
        id="youtube:abc",
        platform="youtube",
        native_id="abc",
        url="https://youtube.com/shorts/abc",
        creator="someone",
        caption="hi",
        posted_at="2026-07-13T10:00:00Z",
        views=10,
        likes=1,
        comments=0,
        source="youtube",
    )
    row = c.as_row()

    assert set(row) == {
        "id", "platform", "native_id", "url", "creator", "caption",
        "posted_at", "views", "likes", "comments", "source",
    }


def test_youtube_source_maps_search_results():
    payload = json.loads(Path("tests/fixtures/youtube_search.json").read_text())
    http = _FakeHttp(payload)
    source = youtube.YouTubeSource("KEY", http=http)

    got = source.collect(
        Watchlist(creators=[Creator("youtube", "UCxyz")], topics=[]),
        since="2026-07-12T00:00:00Z",
    )

    assert len(got) == 1
    assert got[0].id == "youtube:abc123"
    assert got[0].url == "https://www.youtube.com/shorts/abc123"
    assert got[0].creator == "Kindness Daily"
    assert http.calls[0]["params"]["publishedAfter"] == "2026-07-12T00:00:00Z"


def test_youtube_source_skips_non_youtube_creators():
    http = _FakeHttp({"items": []})
    source = youtube.YouTubeSource("KEY", http=http)

    source.collect(
        Watchlist(creators=[Creator("instagram", "erez.v1")], topics=[]),
        since="2026-07-12T00:00:00Z",
    )

    assert http.calls == []
```

- [ ] **Step 3: Run it to verify it fails**

Run: `uv run pytest tests/test_collect.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.collect'`

- [ ] **Step 4: Implement the port and YouTube collector**

Create `app/collect/__init__.py` (empty).

Create `app/collect/base.py`:

```python
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
```

Create `app/collect/youtube.py`:

```python
"""YouTube Data API — free, official, permanent.

Quota: 100 search.list calls/day, which is far more than one creator list needs.
This source keeps working even when a paid scraper breaks.
"""

import httpx

from app.collect.base import Candidate
from app.config import Watchlist

_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"


class YouTubeSource:
    name = "youtube"

    def __init__(self, api_key: str, *, http: httpx.Client | None = None):
        self._api_key = api_key
        self._http = http or httpx.Client(timeout=30)

    def _search_channel(self, handle: str, since: str) -> list[Candidate]:
        response = self._http.get(
            _SEARCH_URL,
            params={
                "key": self._api_key,
                "channelId": handle,
                "part": "snippet",
                "type": "video",
                "order": "date",
                "publishedAfter": since,
                "maxResults": 10,
            },
        )
        response.raise_for_status()
        return [self._to_candidate(item) for item in response.json().get("items", [])]

    @staticmethod
    def _to_candidate(item: dict) -> Candidate:
        video_id = item["id"]["videoId"]
        snippet = item["snippet"]
        return Candidate(
            id=f"youtube:{video_id}",
            platform="youtube",
            native_id=video_id,
            url=f"https://www.youtube.com/shorts/{video_id}",
            creator=snippet.get("channelTitle"),
            caption=snippet.get("title"),
            posted_at=snippet.get("publishedAt"),
            views=None,
            likes=None,
            comments=None,
            source="youtube",
        )

    def collect(self, watchlist: Watchlist, *, since: str) -> list[Candidate]:
        found: list[Candidate] = []
        for creator in watchlist.creators:
            if creator.platform != "youtube":
                continue
            found.extend(self._search_channel(creator.handle, since))
        return found
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_collect.py -v`
Expected: 3 passed

- [ ] **Step 6: Implement the scraper collector from the spike's findings**

Create `app/collect/scraper.py` implementing `Source` for Instagram and TikTok against
whichever vendor won Step 1. Mirror `youtube.py`'s shape exactly: constructor takes
`(api_key, *, http=None)`, `collect()` skips creators whose platform it doesn't serve,
a static `_to_candidate` maps the vendor payload to `Candidate`.

Requirements:
- Record a `provider_usage` row per API call with the vendor's own reported unit cost.
- Cache responses in SQLite keyed by `(creator, day)` so a re-run costs zero units.
- On HTTP error, log and return `[]` — one dead vendor must not kill the digest.
- Write `tests/test_scraper.py` with a fixture captured from the spike's real response.

- [ ] **Step 7: Commit**

```bash
git add app/collect tests/test_collect.py tests/test_scraper.py tests/fixtures/ docs/vendor-spike.md
git commit -m "feat: collector port with free YouTube source and vendor-backed scraper"
```

---

### Task 10: Velocity ranking

**Files:**
- Create: `app/digest/rank.py`
- Test: `tests/test_rank.py`

**Interfaces:**
- Consumes: `base.Candidate`
- Produces:
  - `rank.velocity(candidate, *, now: str) -> float` — views per hour since posting
  - `rank.top_n(candidates, *, n: int, now: str) -> list[Candidate]` — deduped, ranked

- [ ] **Step 1: Write the failing test**

Create `tests/test_rank.py`:

```python
from app.collect.base import Candidate
from app.digest import rank

NOW = "2026-07-14T12:00:00Z"


def _c(cid, views, posted_at):
    return Candidate(
        id=cid, platform="tiktok", native_id=cid, url=f"https://x/{cid}",
        creator=None, caption=None, posted_at=posted_at, views=views,
        likes=None, comments=None, source="scraper",
    )


def test_velocity_is_views_per_hour():
    c = _c("a", 12_000, "2026-07-14T00:00:00Z")  # 12 hours old
    assert rank.velocity(c, now=NOW) == 1000.0


def test_velocity_of_brand_new_video_does_not_divide_by_zero():
    c = _c("a", 500, NOW)
    assert rank.velocity(c, now=NOW) > 0


def test_velocity_is_zero_without_data():
    assert rank.velocity(_c("a", None, NOW), now=NOW) == 0.0
    assert rank.velocity(_c("a", 100, None), now=NOW) == 0.0


def test_top_n_ranks_by_velocity_and_dedupes():
    slow = _c("slow", 1_000, "2026-07-13T12:00:00Z")   # 24h -> ~42/h
    fast = _c("fast", 10_000, "2026-07-14T10:00:00Z")  # 2h  -> 5000/h
    got = rank.top_n([slow, fast, fast], n=2, now=NOW)

    assert [c.id for c in got] == ["fast", "slow"]
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_rank.py -v`
Expected: FAIL — `ImportError: cannot import name 'rank'`

- [ ] **Step 3: Implement ranking**

Create `app/digest/rank.py`:

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_rank.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add app/digest/rank.py tests/test_rank.py
git commit -m "feat: velocity-based candidate ranking"
```

---

### Task 11: Digest web page

**Files:**
- Create: `app/digest/page.py`, `web/template.html`
- Test: `tests/test_page.py`, `tests/fixtures/digest_items.json`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `page.render(body_he: str, items: list[dict], *, for_date: str) -> str` — full HTML
  - `page.write(html: str, out_dir: str, for_date: str) -> str` — returns path
  - `python -m app.digest.page --from-fixtures` — renders from fixtures, zero API keys

**Why this exists in phase 1:** WhatsApp caps a template at 1024 characters, so the digest
can never live in the message — it must be a link. Building the page now means the
WhatsApp switch in phase 2 is a notifier change, not a redesign. It is also simply a
better way to read a digest full of videos.

- [ ] **Step 1: Write the failing test**

Create `tests/fixtures/digest_items.json`:

```json
[
  {
    "url": "https://www.instagram.com/reel/DY2QmhAoF-z/",
    "creator": "andrejko.epta",
    "views": 2400000,
    "analysis": {
      "hook": "הילד רץ אחרי המשאית",
      "why_it_worked": "רגע אמיתי בלי בימוי",
      "transferable_idea": "לצלם את הרגע לפני ההפתעה"
    }
  }
]
```

Create `tests/test_page.py`:

```python
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
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_page.py -v`
Expected: FAIL — `ImportError: cannot import name 'page'`

- [ ] **Step 3: Implement the page**

Create `web/template.html`:

```html
<!doctype html>
<html dir="rtl" lang="he">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>הדוח של {{DATE}}</title>
<style>
  :root { --bg:#FAF5EC; --surface:#FFF; --ink:#2B221A; --soft:#6E6155; --line:#E4D9C8; --accent:#E8622C; }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#211B15; --surface:#2B241D; --ink:#F2EAE0; --soft:#B3A594; --line:#463C30; --accent:#F07A42; }
  }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--ink); line-height:1.65;
         font-family: system-ui, -apple-system, "Segoe UI", Roboto, "Noto Sans Hebrew", Arial, sans-serif; }
  .wrap { max-width:620px; margin:0 auto; padding:28px 20px 60px; }
  h1 { font-size:28px; font-weight:800; margin:0 0 4px; }
  .date { color:var(--soft); font-size:15px; margin:0 0 24px; }
  .body { font-size:17px; white-space:pre-wrap; margin-bottom:32px; }
  .card { background:var(--surface); border:1px solid var(--line); border-radius:14px;
          padding:16px; margin-bottom:12px; }
  .meta { font-size:13px; color:var(--soft); margin-bottom:8px; font-variant-numeric:tabular-nums; }
  .hook { font-weight:700; margin:0 0 6px; }
  .why { margin:0 0 8px; }
  .idea { background:var(--bg); border-radius:10px; padding:10px 12px; font-size:15px; }
  a { color:var(--accent); }
</style>
</head>
<body>
<div class="wrap">
  <h1>הדוח של הבוקר</h1>
  <p class="date">{{DATE}}</p>
  <div class="body">{{BODY}}</div>
  {{CARDS}}
</div>
</body>
</html>
```

Create `app/digest/page.py`:

```python
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
    return f"""
  <div class="card">
    <div class="meta">{views_text}{html.escape(str(item.get("creator") or ""))}</div>
    <p class="hook">{html.escape(str(analysis.get("hook") or ""))}</p>
    <p class="why">{html.escape(str(analysis.get("why_it_worked") or ""))}</p>
    <div class="idea">💡 {html.escape(str(analysis.get("transferable_idea") or ""))}</div>
    <p><a href="{html.escape(str(item.get("url") or ""))}" target="_blank" rel="noopener">לצפייה בסרטון</a></p>
  </div>"""


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
    items = json.loads(
        Path("tests/fixtures/digest_items.json").read_text(encoding="utf-8")
    )
    out = write(
        render("תצוגה מקדימה מקבצי דוגמה.", items, for_date="preview"),
        "web/out",
        "preview",
    )
    print(f"Wrote {out} — open it in a browser.")


if __name__ == "__main__":
    if "--from-fixtures" in sys.argv:
        _preview()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_page.py -v`
Expected: 4 passed

- [ ] **Step 5: Verify the offline sandbox works**

Run: `make digest-preview && open web/out/preview.html`
Expected: a Hebrew RTL page renders. **This command must work with no `.env` at all —
it is Erez's zero-risk playground.**

- [ ] **Step 6: Commit**

```bash
git add app/digest/page.py web/template.html tests/test_page.py tests/fixtures/digest_items.json
git commit -m "feat: Hebrew digest web page with offline preview"
```

---

### Task 12: The daily job, scheduler, and dead-man's-switch

**Files:**
- Create: `app/jobs.py`
- Modify: `app/main.py`
- Test: `tests/test_jobs.py`

**Interfaces:**
- Consumes: everything above
- Produces:
  - `jobs.run_digest(*, deps, sources, notifier, settings, watchlist, compose_digest, template, now: str) -> str | None` — returns the digest body, or `None` if nothing was worth reporting
  - `jobs.deadman_check(*, conn, admin_notifier, for_date: str, now: str) -> None`
  - `main.start_scheduler(deps) -> None`

- [ ] **Step 1: Write the failing test**

Create `tests/test_jobs.py`:

```python
from app import jobs
from app.collect.base import Candidate
from app.store import db

NOW = "2026-07-14T04:00:00Z"


class _FakeNotifier:
    def __init__(self):
        self.sent = []

    def send(self, text):
        self.sent.append(text)


class _FakeSource:
    name = "fake"

    def __init__(self, candidates, boom=False):
        self._candidates = candidates
        self._boom = boom

    def collect(self, watchlist, *, since):
        if self._boom:
            raise RuntimeError("vendor down")
        return self._candidates


def _candidate(cid="tiktok:1"):
    return Candidate(
        id=cid, platform="tiktok", native_id="1", url="https://x/1",
        creator="c", caption=None, posted_at="2026-07-14T00:00:00Z",
        views=10_000, likes=None, comments=None, source="fake",
    )


def _settings():
    return {
        "digest": {"max_videos": 3, "deadman_minute": 30},
        "collect": {"lookback_hours": 48},
    }


def _deps(tmp_path):
    from app import bot
    from app.analyze import fetch

    return bot.Deps(
        conn=db.connect(":memory:"),
        gemini_client=object(),
        claude_client=object(),
        rubric="r",
        persona="p",
        work_dir=str(tmp_path),
        now=lambda: NOW,
        download=lambda url, dest, runner=None: fetch.FetchResult(
            path=str(tmp_path / "v.mp4"), duration_seconds=20.0
        ),
        analyze=lambda path, rubric, client: {"hook": "h", "why_it_worked": "w"},
        compose_reply=lambda a, p, c: "reply",
    )


def test_run_digest_sends_and_records(tmp_path):
    deps = _deps(tmp_path)
    notifier = _FakeNotifier()

    body = jobs.run_digest(
        deps=deps,
        sources=[_FakeSource([_candidate()])],
        notifier=notifier,
        settings=_settings(),
        watchlist=None,
        compose_digest=lambda items, template, client: "דוח הבוקר",
        template="t",
        now=NOW,
    )

    assert body == "דוח הבוקר"
    assert len(notifier.sent) == 1
    row = deps.conn.execute("SELECT sent_at FROM digests WHERE for_date='2026-07-14'").fetchone()
    assert row["sent_at"] is not None


def test_run_digest_survives_a_dead_source(tmp_path):
    deps = _deps(tmp_path)
    notifier = _FakeNotifier()

    body = jobs.run_digest(
        deps=deps,
        sources=[_FakeSource([], boom=True), _FakeSource([_candidate()])],
        notifier=notifier,
        settings=_settings(),
        watchlist=None,
        compose_digest=lambda items, template, client: "דוח",
        template="t",
        now=NOW,
    )

    assert body == "דוח"  # one vendor down must not kill the morning


def test_run_digest_says_so_when_nothing_found(tmp_path):
    deps = _deps(tmp_path)
    notifier = _FakeNotifier()

    body = jobs.run_digest(
        deps=deps,
        sources=[_FakeSource([])],
        notifier=notifier,
        settings=_settings(),
        watchlist=None,
        compose_digest=lambda items, template, client: "unused",
        template="t",
        now=NOW,
    )

    assert body is None
    assert "לא מצאתי" in notifier.sent[0]  # degrade loudly, never silently


def test_deadman_alerts_admin_when_digest_missing():
    conn = db.connect(":memory:")
    admin = _FakeNotifier()

    jobs.deadman_check(conn=conn, admin_notifier=admin, for_date="2026-07-14", now=NOW)

    assert len(admin.sent) == 1
    assert "2026-07-14" in admin.sent[0]


def test_deadman_is_quiet_when_digest_was_sent():
    conn = db.connect(":memory:")
    conn.execute(
        "INSERT INTO digests (for_date, body_he, sent_at, created_at) VALUES (?,?,?,?)",
        ("2026-07-14", "x", NOW, NOW),
    )
    conn.commit()
    admin = _FakeNotifier()

    jobs.deadman_check(conn=conn, admin_notifier=admin, for_date="2026-07-14", now=NOW)

    assert admin.sent == []
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_jobs.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.jobs'`

- [ ] **Step 3: Implement the job**

Create `app/jobs.py`:

```python
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
    videos.save_analysis(
        deps.conn, candidate.id, gemini.RUBRIC_VERSION, analysis, now=deps.now()
    )
    usage.record(
        deps.conn, "gemini", "analyze_video", 1,
        gemini.estimate_cost(result.duration_seconds), now=deps.now(),
    )
    return analysis


def run_digest(
    *, deps, sources, notifier, settings, watchlist, compose_digest, template, now: str
) -> str | None:
    """Collect, rank, analyze, compose, publish, send. Returns the body, or None."""
    for_date = now[:10]
    candidates = _collect_all(sources, watchlist, since=_since(now, settings))
    picked = rank.top_n(
        candidates, n=settings["digest"]["max_videos"], now=now
    )

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
    notifier.send(body)
    return body


def _since(now: str, settings: dict) -> str:
    from datetime import datetime, timedelta

    parsed = datetime.strptime(now, "%Y-%m-%dT%H:%M:%SZ")
    hours = settings["collect"]["lookback_hours"]
    return (parsed - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")


def deadman_check(*, conn, admin_notifier, for_date: str, now: str) -> None:
    """Runs at 07:30. If no digest went out, Elik hears about it before Erez does."""
    row = conn.execute(
        "SELECT sent_at FROM digests WHERE for_date = ?", (for_date,)
    ).fetchone()
    if row and row["sent_at"]:
        return
    admin_notifier.send(f"⚠️ No digest went out for {for_date}. Check the logs.")
    log.error("Dead-man's-switch fired for %s", for_date)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_jobs.py -v`
Expected: 5 passed

- [ ] **Step 5: Wire the scheduler into main**

In `app/main.py`, add these imports at the top. `compose` and `config` are already
imported from Task 7 — don't add them twice:

```python
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app import jobs
from app.collect.youtube import YouTubeSource
from app.notify.telegram import TelegramNotifier
```

Then add this function, and call `start_scheduler(app.bot_data["deps"])` inside `main()`
immediately before `app.run_polling()`:

```python
def start_scheduler(deps: bot.Deps) -> None:
    """APScheduler in-process: no cron, no second system to learn."""
    settings = config.load_settings()
    token = config.env("TELEGRAM_BOT_TOKEN")
    erez = TelegramNotifier(token, config.env("TELEGRAM_CHAT_ID_EREZ"))
    admin = TelegramNotifier(token, config.env("TELEGRAM_CHAT_ID_ADMIN"))
    sources = [YouTubeSource(config.env("YOUTUBE_API_KEY"))]

    scheduler = BackgroundScheduler(timezone="Asia/Jerusalem")

    def _digest_job() -> None:
        jobs.run_digest(
            deps=deps,
            sources=sources,
            notifier=erez,
            settings=settings,
            watchlist=config.load_watchlist(),
            compose_digest=compose.write_digest,
            template=config.load_prompt("digest"),
            now=bot.utc_now(),
        )

    def _deadman_job() -> None:
        jobs.deadman_check(
            conn=deps.conn,
            admin_notifier=admin,
            for_date=bot.utc_now()[:10],
            now=bot.utc_now(),
        )

    scheduler.add_job(
        _digest_job,
        CronTrigger(hour=settings["digest"]["hour"], minute=settings["digest"]["minute"]),
        id="daily_digest",
    )
    scheduler.add_job(
        _deadman_job,
        CronTrigger(
            hour=settings["digest"]["hour"], minute=settings["digest"]["deadman_minute"]
        ),
        id="deadman",
    )
    scheduler.start()
    log.info("Scheduler started: digest at %02d:00 Asia/Jerusalem", settings["digest"]["hour"])
```

- [ ] **Step 6: Verify the job runs on demand**

Run:

```bash
uv run python -c "
from app.main import build_deps
from app import bot, config, jobs
from app.collect.youtube import YouTubeSource
from app.digest import compose
from app.notify.telegram import TelegramNotifier
deps = build_deps()
body = jobs.run_digest(
    deps=deps,
    sources=[YouTubeSource(config.env('YOUTUBE_API_KEY'))],
    notifier=TelegramNotifier(config.env('TELEGRAM_BOT_TOKEN'), config.env('TELEGRAM_CHAT_ID_ADMIN')),
    settings=config.load_settings(),
    watchlist=config.load_watchlist(),
    compose_digest=compose.write_digest,
    template=config.load_prompt('digest'),
    now=bot.utc_now(),
)
print(body)
"
```

Expected: a Hebrew digest arrives in the admin Telegram chat, and `web/out/<today>.html`
exists. Open the page.

- [ ] **Step 7: Commit**

```bash
git add app/jobs.py app/main.py tests/test_jobs.py
git commit -m "feat: daily 07:00 digest job with dead-man's-switch"
```

---

### Task 13: /costs command

**Files:**
- Modify: `app/main.py`
- Test: `tests/test_costs.py`

**Interfaces:**
- Consumes: `store.usage.month_to_date`
- Produces: `bot.costs_message(conn, *, month: str) -> str`

- [ ] **Step 1: Write the failing test**

Create `tests/test_costs.py`:

```python
from app import bot
from app.store import db, usage


def test_costs_message_lists_providers_and_total():
    conn = db.connect(":memory:")
    usage.record(conn, "gemini", "analyze_video", 1, 0.02, now="2026-07-01T00:00:00Z")
    usage.record(conn, "claude", "write_digest", 1, 0.15, now="2026-07-02T00:00:00Z")

    msg = bot.costs_message(conn, month="2026-07")

    assert "gemini" in msg and "claude" in msg
    assert "0.17" in msg


def test_costs_message_when_nothing_spent():
    conn = db.connect(":memory:")

    msg = bot.costs_message(conn, month="2026-07")

    assert "עדיין לא" in msg
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_costs.py -v`
Expected: FAIL — `AttributeError: module 'app.bot' has no attribute 'costs_message'`

- [ ] **Step 3: Implement it**

Append to `app/bot.py`:

```python
def costs_message(conn, *, month: str) -> str:
    """Spend so far this month, in chat, before the credit card says anything."""
    rows = usage.month_to_date(conn, month)
    if not rows:
        return f"עדיין לא הוצאנו כלום ב-{month}."
    lines = [f"💰 ההוצאות ב-{month}:", ""]
    total = 0.0
    for row in rows:
        total += row["cost_usd"]
        lines.append(f"  {row['provider']}: ${row['cost_usd']:.2f} ({row['calls']} קריאות)")
    lines += ["", f"סה״כ: ${total:.2f}"]
    return "\n".join(lines)
```

In `app/main.py`, add the handler function and register it in `main()` next to the
`/start` handler:

```python
async def on_costs(update: Update, ctx) -> None:
    from datetime import datetime, timezone

    month = datetime.now(timezone.utc).strftime("%Y-%m")
    await update.message.reply_text(
        bot.costs_message(ctx.bot_data["deps"].conn, month=month)
    )
```

```python
    app.add_handler(CommandHandler("costs", on_costs))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_costs.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add app/bot.py app/main.py tests/test_costs.py
git commit -m "feat: /costs command surfaces spend in chat"
```

---

### Task 14: Erez's on-ramp — dev bot, lessons, good-first-issues

**Files:**
- Create: `docs/learn/02-the-prompts-are-yours.md`, `docs/learn/03-your-first-code.md`, `.env.dev.example`, `docs/good-first-issues.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: everything
- Produces: Erez can run the system locally against a dev bot that physically cannot reach
  the real chat, with no prod secrets on his machine

- [ ] **Step 1: Create the dev-bot separation**

Create `.env.dev.example`:

```
# ארז — זה הקובץ שלך. תעתיק אותו ל-.env
#
# הבוט הניסיוני שלך. הוא לא יכול לשלוח הודעות לצ'אט האמיתי —
# הוא בוט אחר לגמרי. תשבור אותו כמה שאתה רוצה.
TELEGRAM_BOT_TOKEN=<אליק ייתן לך טוקן של בוט dev>
TELEGRAM_CHAT_ID_EREZ=<ה-chat id שלך מול הבוט הניסיוני>
TELEGRAM_CHAT_ID_ADMIN=<אותו דבר>

# מפתח Gemini עם תקרת הוצאה. אם תשרוף אותו — לא נורא.
GEMINI_API_KEY=<אליק ייתן לך>

# בלי מפתח Claude. לפיתוח מקומי לא צריך.
ANTHROPIC_API_KEY=

YOUTUBE_API_KEY=<אליק ייתן לך>
SCRAPER_API_KEY=

DB_PATH=data/dev.db
```

- [ ] **Step 2: Write the remaining lessons**

Create `docs/learn/02-the-prompts-are-yours.md`:

````markdown
# 2. הטקסטים הם שלך (5 דקות)

## מה יש בתיקייה prompts/

שלושה קבצים. כולם עברית. כולם שלך:

| קובץ | מה הוא עושה |
|---|---|
| `analysis_rubric.md` | אומר ל-AI מה לחפש בסרטון |
| `digest.md` | אומר ל-AI איך לכתוב את הדוח של הבוקר |
| `bot_persona.md` | אומר ל-AI איך לדבר איתך |

## איך זה עובד

הקוד לא יודע עברית. הוא רק **קורא את הקובץ** ושולח אותו ל-AI. זהו.
זה אומר שאתה יכול לשנות איך המערכת מתנהגת **בלי לגעת בקוד**.

## תרגיל

1. תפתח את `prompts/digest.md`.
2. תוסיף שורה למבנה:

```
4. **הסרטון הכי מוזר שראיתי היום** — משהו שאין לו הסבר. רק בשביל הכיף.
```

3. Commit, PR, אליק מאשר.
4. מחר בבוקר — יש לך סעיף חדש בדוח.

**שינית התנהגות של מערכת בייצור. בלי קוד.**

## טיפ

תשאל את Claude: "תסתכל על prompts/digest.md ותציע לי 3 שיפורים".
הוא יקרא את הקובץ ויענה בעברית.
````

Create `docs/learn/03-your-first-code.md`:

````markdown
# 3. הקוד הראשון שלך (5 דקות + שיחה אחת עם Claude)

## קודם — הסביבה

```bash
git clone https://github.com/eliktz/erez-video-assistant.git
cd erez-video-assistant
make setup
```

תעתיק את `.env.dev.example` ל-`.env`. אליק ייתן לך את המפתחות.
**שים לב: זה בוט אחר.** הוא לא יכול לשלוח הודעות לצ'אט האמיתי שלך. תשבור כמה שבא לך.

## מגרש המשחקים

```bash
make digest-preview
```

זה מייצר דוח לדוגמה **בלי חיבור לשום דבר**. בלי מפתחות, בלי כסף, בלי סיכון.
תפתח את `web/out/preview.html` בדפדפן.

## שתי הפקודות שחשוב לזכור

```bash
make test    # לפני כל push. אם זה אדום — משהו נשבר.
make lint    # מסדר את הקוד
```

## התרגיל

תפתח את הרשימה ב-`docs/good-first-issues.md`, תבחר משימה,
ותגיד ל-Claude Code:

> "תקרא את CLAUDE.md ואת docs/good-first-issues.md, ותעשה את משימה מספר 1.
> תסביר לי בעברית כל שינוי שאתה עושה."

אחרי שזה עובד: `make test`, ואז Commit ו-PR.

## אם שברת משהו

אי אפשר. באמת:
- הבוט הניסיוני שלך מנותק מהצ'אט האמיתי.
- ה-CI חוסם PR שנשבר.
- Railway חוזר אחורה בלחיצה אחת.

הכי גרוע שיקרה — אליק יגיד "זה לא עובד, בוא ננסה אחרת".
````

- [ ] **Step 3: Write the good-first-issues list**

Create `docs/good-first-issues.md`:

```markdown
# משימות ראשונות לארז

כל משימה פה בגודל של **שיחה אחת עם Claude Code**. לא יותר.
תבחר אחת, תעשה אותה, תפתח PR.

---

## 1. להוסיף פקודת /help לבוט

**מה:** כשאתה שולח `/help` — הבוט מסביר בעברית מה הוא יודע לעשות.
**איפה:** `app/main.py`, ליד `on_start`.
**איך לבדוק:** `make test`, ואז `make run` ותשלח `/help` לבוט הניסיוני.

---

## 2. להוסיף את מספר הצפיות לניתוח בצ'אט

**מה:** כשהבוט מנתח סרטון, שיגיד גם כמה צפיות יש לו.
**איפה:** `app/bot.py`, בפונקציה `analyze_url`.
**רמז:** המידע כבר יושב ב-`videos` בבסיס הנתונים.
**איך לבדוק:** תוסיף בדיקה ב-`tests/test_bot.py`.

---

## 3. "סאונד של היום" בדוח

**מה:** סעיף חדש בדוח — איזו מוזיקה חוזרת בסרטונים של הבוקר.
**איפה:** `prompts/digest.md` (בלי קוד!) — ואם צריך, גם `prompts/analysis_rubric.md`.
**איך לבדוק:** `make digest-preview`.

---

## 4. פקודת /idea — הפיצ'ר השלם הראשון שלך

**מה:** `/idea` מחזיר 3 רעיונות לסרטון, מבוססים על הטרנדים של השבוע.
**איפה:** קובץ חדש `prompts/ideas.md` + handler ב-`app/main.py`.
**זה הגדול.** אליק רק יעבור על זה. תעשה אותו כשאתה מרגיש מוכן.
```

- [ ] **Step 4: Update the README**

Create `README.md`:

````markdown
# erez-video-assistant

עוזר AI לארז — מוצא טרנדים ויראליים, מנתח סרטונים, וכותב דוח יומי בעברית.

**ארז — תתחיל כאן:** [`docs/learn/01-what-is-this.md`](docs/learn/01-what-is-this.md)

## Quick start

```bash
make setup            # sync deps
cp .env.example .env  # then fill it in
make test             # run before every push
make digest-preview   # render a sample digest — no keys, no cost
make run              # start the bot
```

## Docs

- Design: [`docs/superpowers/specs/2026-07-14-erez-video-assistant-direction-design.md`](docs/superpowers/specs/2026-07-14-erez-video-assistant-direction-design.md)
- Plan: [`docs/superpowers/plans/2026-07-14-phase-1-digest-and-analysis.md`](docs/superpowers/plans/2026-07-14-phase-1-digest-and-analysis.md)
- Rules for AI pairing: [`CLAUDE.md`](CLAUDE.md)
- Lessons (Hebrew): [`docs/learn/`](docs/learn/)
````

- [ ] **Step 5: Verify the offline path works from a clean clone**

```bash
cd /tmp && rm -rf verify
git clone https://github.com/eliktz/erez-video-assistant.git verify && cd verify
make setup && make test && make digest-preview
```

Expected: all green with **no `.env` present**. That is the point — Erez's sandbox must
never require a secret.

- [ ] **Step 6: Commit**

```bash
git add docs/learn docs/good-first-issues.md .env.dev.example README.md
git commit -m "docs: Erez's on-ramp — dev bot, Hebrew lessons, good-first-issues"
```

---

## Phase 1 exit criteria

Check these before declaring phase 1 done:

- [ ] Erez has received a digest at 07:00 on **five consecutive days**
- [ ] Erez has sent the bot **3+ videos** for on-demand analysis, unprompted
- [ ] The dead-man's-switch has been tested by deliberately breaking the job
- [ ] `/costs` shows month-to-date spend under **$40**
- [ ] Erez's first `watchlist.yaml` PR is **merged and live**
- [ ] `make digest-preview` works from a clean clone with no `.env`
- [ ] The vendor decision is written in `docs/vendor-spike.md` with **measured** units/day

## Deliberately deferred

Not in phase 1. Do not build these here:

| Deferred | Arrives |
|---|---|
| WhatsApp notifier | Phase 2, when Meta's paperwork clears |
| Style profile from Erez's own catalog | Phase 2 |
| `/ideas` command | Phase 2 (Erez builds it — issue #4) |
| Twelve Labs Marengo embeddings | Only if phase 2's cheap style-matching proves insufficient |
| Remotion, Veo, voice cloning | Phase 3 |
| Comment/DM draft-approve | Phase 3 |
| The global AI channel | Phase 4, gated on the AI-disclosure research |
