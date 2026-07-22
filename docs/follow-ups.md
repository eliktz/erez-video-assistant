# Follow-ups after the phase-1 whole-branch review

These are real findings from the phase-1 integration review that we consciously did **not** fix
before merging. The seven Critical ones are fixed (auth gate, secrets-in-logs, digest timezone,
SSRF host check, Gemini upload polling, cross-thread SQLite, dead-man ordering) plus billing,
the cost cap, `@handle` support and `make run`. What is left is listed here so it is tracked
rather than forgotten.

**Do these before the first real 07:00 run.**

---

## 1. YouTube never sets view counts, so ranking is inert  (review #8)

`app/collect/youtube.py::_to_candidate` hardcodes `views=None`, and `app/digest/rank.py::velocity`
returns `0.0` when views are falsy. Every YouTube candidate therefore ties at 0.0 and `top_n`
degenerates to collection order (watchlist order, newest-first per creator).

**Consequence:** a 6-hour-old 1M-view Short can lose to ten mediocre ones. The "velocity beats raw
views" idea — the reason the digest is supposed to be worth reading — does nothing today.
**Fix:** a follow-up `videos.list(part=statistics,id=...)` call to fill `views`, batched over the
ids from `search.list`. Every rank test hand-builds Candidates *with* views, which is why nothing
caught this — add a test using a Candidate as the real collector actually produces it.

## 2. The digest page link is never sent  (review #10)

`app/jobs.py::run_digest` renders and stores `html_path`, then sends only the raw Claude body.
Erez never receives the link to the page phase 1 exists to build.

Two related delivery problems in the same place:
- Telegram `sendMessage` caps at **4096 characters** after parsing, but `write_digest` asks for
  `max_tokens=4000`. A long digest → HTTP 400 → `run_digest` raises. (The dead-man's-switch fires
  correctly, so this fails loudly — but it is a recurring outage.)
- `parse_mode="Markdown"` (legacy) on model-generated Hebrew: one unbalanced `*` or `_` → 400
  "can't parse entities". No escaping, no splitting, no plain-text fallback.

**Fix:** send a short Hebrew intro + the page link; keep the body on the page. Drop legacy
Markdown or escape properly.

## 3. The sync pipeline blocks the bot's event loop  (review #11)

`app/main.py::on_message` is `async` but calls the fully synchronous `bot.analyze_url`, and PTB
defaults to one concurrent update. One uncached video (yt-dlp download + Gemini + Claude, ~30-60s)
freezes **every** other update for the duration — `/costs`, `/start`, everything.
**Fix:** `await asyncio.to_thread(bot.analyze_url, url, deps=...)`.

## 4. The "send me the file" fallback does not exist  (review #12)

`app/bot.py` tells Erez *"נסה לשלוח לי את הקובץ עצמו"* when a download fails, but `app/main.py`
registers handlers only for `/start`, `/costs`, and TEXT. A video/document upload matches no
handler and is met with silence. `fetch.TELEGRAM_MAX_BYTES` is dead code.

This matters more than it looks: Instagram and TikTok blocking yt-dlp is the **expected** case, and
this upload path is the designated mitigation.
**Fix:** a `MessageHandler(filters.VIDEO | filters.Document.VIDEO, ...)` (gated by the same
allowlist) that pulls the file via `getFile` and runs it through the same analysis path.

## 5. Collector metadata can never enrich an on-demand row  (review #14)

`app/store/videos.py::upsert_video`'s `ON CONFLICT` updates only
`views/likes/comments/caption/updated_at`. An on-demand insert writes `creator=NULL`,
`posted_at=NULL`, `source="on_demand"`. When the collector later finds the same video with a real
`creator`/`posted_at`, all of it is discarded — and `posted_at` is velocity's input, so a video
Erez asked about first can never rank. Undermines "the corpus compounds."
**Fix:** COALESCE the collector's values over the nulls.

## 6. ~~`DB_PATH` default silently discards the corpus~~  (review #16) — **RESOLVED 2026-07-17**

Railway now has volume `bot-volume` mounted at `/data` and `DB_PATH=/data/erez.db` set,
so the corpus survives redeploys. The repo-relative default remains for local dev only.

## 7. Files and functions over the size rules  (review #17)

CLAUDE.md says functions under 30 lines and files under ~150 — the rule exists so Erez can read any
function in one sitting.
- `app/main.py::start_scheduler` is 42 lines.
- `app/bot.py` is 182 lines, `app/main.py` is 159.

**Fix:** split URL recognition (`_ALLOWED_HOSTS`, `_URL_PATTERNS`, `URL_RE`, `_host_is_a_platform`,
`video_id_from_url`) out of `bot.py` into its own small module; split scheduler wiring out of `main.py`.

## 8. Hebrew strings inline in Python  (review #D)

CLAUDE.md rule 4 says "Never put Hebrew text in Python", but user-facing Hebrew currently lives in
`bot.py`, `jobs.py`, `main.py`, `page.py` and `compose.py`. Accepted for phase 1 — but the rule as
written is stricter than the code, so either the rule or the code should move.

---

## Status update (2026-07-22)

Done since this list was written: the live Gemini spike + Hebrew quality check (validated
against Erez's own top-5 — see `docs/erez-top5.md`), the real end-to-end Telegram test,
the Railway deploy (volume + env vars), Gemini-only swap, thinking-token billing, empty-reply
guard, PTB error handler + honest failure replies, 503 model fallback, and topic-based
trend collection feeding the (now enabled) daily digest.

**Still open (needs a decision or budget, not just code):**
- **Task 9 Step 1/6 — the scraper vendor spike and the Instagram/TikTok collector.** The
  single biggest gap: Erez's world is Instagram, and the digest can't see it. $49–100/mo
  decision; measure EnsembleData-class vendors, don't guess.
- **Gemini billing** — the key is free tier; 503 storms are its cost. Enabling billing on
  the Google project (~$2–5/mo) moves us to paid capacity if the storms annoy in daily use.
- **Digest quality tuning** — the English topics surface the global staged-kindness genre.
  Sharpening `watchlist.yaml` topics is Erez's highest-leverage edit (and his file).
