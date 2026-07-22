# Operations runbook

Everything you need to run, deploy, and debug this system. Written for whoever
picks this up next — human or AI. Updated 2026-07-22.

## What is running right now

| Thing | Value |
|---|---|
| Host | Railway, project `erez-video-assistant` (id `5af07bfa-3646-44eb-b556-99693c9af562`), account `eliktz@gmail.com` |
| Service | `bot` — one process: Telegram long-polling + APScheduler in-process |
| Storage | Railway volume `bot-volume` mounted at `/data`; SQLite at `/data/erez.db` (survives redeploys) |
| Telegram bot | `@erez_v_assistant_bot` (BotFather owner: Elik). Privacy mode DISABLED so it reads group messages |
| Serves | group **"ארז טרנדים"** `-1004438879848` (Erez + Elik) and Elik's private chat `584144506` (admin alerts). Everyone else is silently ignored |
| Schedule | digest **07:00 Asia/Jerusalem** to the group; dead-man check **07:30** → alerts the ADMIN chat if no digest went out |
| AI | Gemini only. Analysis + Hebrew prose: `gemini-3.5-flash`, auto-fallback `gemini-flash-lite-latest` on 503. Claude was dropped 2026-07-16 (cost; Hebrew verified good) |

## Deploying

Deploys are **manual from a local clone** — the Railway service is NOT linked to
GitHub. "Merged to main" and "deployed" are two different steps; keep them in sync.

```bash
brew install railway            # once
railway login                   # once, opens browser (needs access to the Railway project)
railway link                    # once per clone: pick erez-video-assistant, then:
railway service bot             # bind this directory to the service

git checkout main && git pull   # deploy ONLY merged main
railway up --detach             # build + deploy (~90s)
railway logs                    # confirm: "Bot starting (long polling); answering 2 authorized chat(s)"
```

Rollback: Railway dashboard → service `bot` → Deployments → Redeploy a previous build.

Env vars live ONLY in Railway (dashboard → service → Variables) and in the local
gitignored `.env`. Names: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID_EREZ`,
`TELEGRAM_CHAT_ID_ADMIN`, `GEMINI_API_KEY`, `YOUTUBE_API_KEY`, `DB_PATH=/data/erez.db`.
Never commit a secret — gitleaks in CI blocks the PR.

## Local development

```bash
make setup             # uv sync — NEVER delete uv.lock or .venv (see gotchas)
cp .env.example .env   # fill in; make run loads it via uv run --env-file
make test              # 66 tests, <2s — run before every push
make lint              # ruff
make digest-preview    # offline sample digest, zero keys, zero cost
make run               # run the bot locally — READ THE NEXT PARAGRAPH FIRST
```

**One poller per token.** Telegram allows a single `getUpdates` consumer. If the
Railway bot is running and you `make run` locally, they fight (409s / missed
updates). For local testing either create a separate dev bot via BotFather
(`.env.dev.example`) or scale the Railway service to 0 first.

## Gotchas that already cost us hours

- **Telegram group IDs change.** When a group is upgraded to a supergroup
  (adding/removing members can trigger this), its chat id changes
  (`-539…` → `-100…`). Symptom: the bot goes silent in the group with nothing in
  the logs (the allowlist filter drops unknown chats). Fix: get the new id
  (`sendChatAction` to the old id returns `migrate_to_chat_id`), update
  `TELEGRAM_CHAT_ID_EREZ` on Railway, redeploy.
- **Gemini model IDs rot.** `gemini-2.5-flash` is retired for new API keys (404
  "no longer available to new users"). Current: `gemini-3.5-flash`. If it ever
  404s, list live models (`client.models.list()`) and update `MODEL` in
  `app/analyze/gemini.py`.
- **Free-tier 503 storms are normal.** The Gemini key is free tier; under load
  Google sheds unpaid traffic ("503 high demand"), sometimes for minutes. The code
  falls back to `gemini-flash-lite-latest` automatically and tells the user to
  retry if both fail. If this bites daily, enable billing on the Google project
  (~$2–5/month at current volume) — paid capacity barely 503s.
- **Thinking tokens are billed.** Gemini reasoning models report
  `thoughts_token_count` separately and Google bills them as output. Any cost math
  must include them (`compose.estimate_cost` does — a one-line reply once showed
  20 visible tokens and 533 thinking tokens).
- **YouTube blocks datacenter IPs.** yt-dlp from Railway gets "Sign in to confirm
  you're not a bot" (cookies would "fix" it — forbidden by doctrine). That is why
  YouTube videos are analyzed WITHOUT downloading: the URL goes to Gemini as
  `file_data` and Google fetches it server-side (`gemini.analyze_youtube`). yt-dlp
  remains only as a fallback and for other platforms/local dev.
- **yt-dlp:** the real info dict has no `_filename`; the saved path is
  `requested_downloads[0].filepath`. Instagram/TikTok downloads usually fail
  logged-out (expected — see Deferred). NEVER add cookies or Erez's session.
- **On Elik's Mac specifically:** the PATH `uv`/`python3` are x86_64 (Rosetta) on
  an arm64 machine. `uv.lock` + `.venv` make everything fast; deleting them
  triggers a ~2-minute re-resolve per command and an arch-mismatch rabbit hole.

## Money

Every paid API call writes a `provider_usage` row (hard project rule). `/costs`
in Telegram shows month-to-date. A `cost.monthly_cap_usd` (settings.yaml, $40)
is enforced in code before any paid work — bot replies and the digest stop when
it is hit. Current burn: ~$0.006 per on-demand analysis, ~$0.05/day for the digest.

## The daily digest

Fuel: `config/watchlist.yaml` (Erez-owned). Two inputs:
- `creators` with `platform: youtube` — checked 2026-07-17: Erez's Instagram
  creators have no living YouTube channels, so today this contributes ~nothing.
- `topics` — the real fuel. Each topic is searched for the most-viewed shorts of
  the last 48h (`order=viewCount`, `videoDuration=short`). English topics surface
  the global staged-kindness genre; sharpening the topics list is the highest-leverage
  digest-quality edit and it is Erez's file.

Flow: collect → rank (`app/digest/rank.py`) → analyze up to `max_videos` →
compose Hebrew → send to group → write `digests` row. `sent_at` is written only
after a successful send, which is what the 07:30 dead-man check reads.

## Deferred / known gaps

See [`docs/follow-ups.md`](follow-ups.md) for the tracked list. Headlines:
- **Instagram/TikTok monitoring needs a paid scraper vendor** (EnsembleData-class,
  $49–100/mo). The spike was never run; until then the digest sees YouTube only.
  On-demand links from IG usually fail to download logged-out (by design we never
  use Erez's account) — the planned mitigation is a file-upload handler (not built).
- YouTube collector sets `views=None`, so velocity ranking degenerates to
  recency — needs a `videos.list(part=statistics)` follow-up call.
- The digest HTML page is written and stored but the link is never sent; long
  digests can exceed Telegram's 4096-char cap.

## Repo map

Erez owns `prompts/*.md` and `config/*.yaml` (all Hebrew lives there).
Design: `docs/superpowers/specs/…direction-design.md`. Phase-1 plan:
`docs/superpowers/plans/…phase-1-digest-and-analysis.md`. Hebrew lessons for
Erez: `docs/learn/`. His starter tasks: `docs/good-first-issues.md`.
