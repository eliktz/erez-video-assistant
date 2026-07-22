# erez-video-assistant

עוזר AI לארז — מוצא טרנדים ויראליים, מנתח סרטונים, וכותב דוח יומי בעברית.

**ארז — תתחיל כאן:** [`docs/learn/01-what-is-this.md`](docs/learn/01-what-is-this.md)

## Where things stand (2026-07-22)

- **Live in production** on Railway: Telegram bot `@erez_v_assistant_bot`, serving the
  shared group. Send it a video link → Hebrew analysis in ~20s.
- **Daily digest enabled**: 07:00 Asia/Jerusalem, fueled by the topics in
  `config/watchlist.yaml`; a 07:30 dead-man alert covers silent failures.
- **One AI vendor**: Gemini (`gemini-3.5-flash`, auto-fallback to lite on 503) does both
  the video analysis and the Hebrew prose. Verified against Erez's own top videos.
- **Not built yet**: Instagram/TikTok monitoring (needs a paid scraper vendor — spike
  pending). Tracked gaps: [`docs/follow-ups.md`](docs/follow-ups.md).

**Continuing the work? Read [`docs/operations.md`](docs/operations.md) first** — how to
deploy, the env vars, and the gotchas that already cost us hours (Telegram group-ID
migration, Gemini model retirement, free-tier 503 storms).

## Quick start

```bash
make setup            # sync deps (uv)
cp .env.example .env  # then fill in the keys
make test             # run before every push
make digest-preview   # render a sample digest — no keys, no cost
make run              # run the bot locally — see docs/operations.md re: one poller per token
```

## Docs

- **Operations runbook**: [`docs/operations.md`](docs/operations.md)
- Design: [`docs/superpowers/specs/2026-07-14-erez-video-assistant-direction-design.md`](docs/superpowers/specs/2026-07-14-erez-video-assistant-direction-design.md)
- Plan (phase 1, executed): [`docs/superpowers/plans/2026-07-14-phase-1-digest-and-analysis.md`](docs/superpowers/plans/2026-07-14-phase-1-digest-and-analysis.md)
- Known gaps / fast-follows: [`docs/follow-ups.md`](docs/follow-ups.md)
- Rules for AI pairing: [`CLAUDE.md`](CLAUDE.md)
- Lessons for Erez (Hebrew): [`docs/learn/`](docs/learn/), starter tasks: [`docs/good-first-issues.md`](docs/good-first-issues.md)
