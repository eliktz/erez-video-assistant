# erez-video-assistant — Direction & Architecture Design

**Date:** 2026-07-14
**Status:** Approved (direction), pending implementation plan
**Author:** Elik Katz (with Claude)

---

## 1. What this is

An AI assistant system for **Erez** ([@erez.v1](https://www.instagram.com/erez.v1/)), an Israeli creator of viral
feel-good short videos — real street footage, hidden acts of kindness, genuine human encounters, in Hebrew.

**Elik builds it. Erez learns to build it.** That second clause is a design constraint, not a nice-to-have:
Erez's own stated #1 goal for the next six months is *"ללמוד AI וליצור סוגי תוכן חדשים"* — to learn AI and
create new kinds of content. The system is therefore designed as a teaching vehicle first and a product second.

### Success criteria (3 months)

| # | Criterion | How we know |
|---|---|---|
| a | Erez reads a daily Hebrew trend digest | He opens it most mornings, unprompted |
| b | He asks the bot to analyze a few videos a week | Usage logs |
| c | **Erez starts developing the system himself**, with Elik's occasional help | One merged PR he wrote without Elik writing code |

Criterion (c) is the one that decides the architecture. Criterion (a) is the one that fails most easily —
a boring digest is an unread digest.

---

## 2. What Erez asked for

From his questionnaire (2026-07-14, [source](https://eliktz.github.io/erez-questionnaire/)):

- **Daily 07:00 report** on what viral content is "burning up the networks"
- **Watch his favorite creators' pages** — go over what they posted, understand why their strong videos
  succeeded or failed, deep analysis with clear summaries against predefined parameters.
  (Referenced: [andrejko.epta](https://www.instagram.com/andrejko.epta))
- **Creative ideas that fit his content world** — the moving, uplifting one — adapted for the Israeli audience
- **Strong hooks, "פרות סגולות"** (purple cows), scroll-stopping ideas nobody has seen
- **Reply to comments and DMs** across Instagram, TikTok, Facebook, YouTube — **as drafts he approves** (his explicit choice)
- **Content prepared a month ahead**, auto-published to all networks
- **AI additions to his own videos** to make them more viral and distinctive
- **A new AI-generated channel for a global audience** — advocacy/narrative content about Israel
- **Voice cloning: yes**, he wants it ("מגניב, בא לי")
- **Interface: WhatsApp**, not Telegram
- Everything drains him today: ideas, filming, editing, captions, publishing, replying

His best-performing video: https://www.instagram.com/reel/DY2QmhAoF-z/

---

## 3. Verified research findings

Three deep-research rounds against live primary sources (2026-07-13/14). Figures are as-of those dates and
vendor pricing moves — re-check before committing spend.

### Data access
- **TikTok Research API is closed to us.** Academic/non-profit only; US/EEA/UK/Switzerland/Brazil only; applicants
  must be "independent from commercial interests." An Israeli commercial project is excluded twice over.
  ([TikTok](https://developers.tiktok.com/products/research-api/))
- **EnsembleData** covers TikTok + Instagram Reels + YouTube Shorts with hashtag/keyword/music search and per-account
  endpoints. Free trial 50 units/day; **Wood $100/mo** (1,500 units/day); Bronze $200/mo (5,000/day).
  ([pricing](https://ensembledata.com/pricing))
- **YouTube Data API is free and official** — permanent third source. 100 `search.list`/day, 100 `videos.insert`/day,
  10,000 units/day for everything else. ([Google](https://developers.google.com/youtube/v3/getting-started))
- **Legal gradient** (from *Meta v. Bright Data*, N.D. Cal. 2024 — summary judgment for Bright Data, Meta dismissed
  and waived appeal; and *hiQ v. LinkedIn* — CFAA-safe but lost on contract):
  logged-out public scraping = low contract risk → account/cookie-based scraping = contract + ban exposure →
  **scraping with Erez's own account = highest risk. Never do it.**

### Analysis (cheap)
- **Gemini Flash** takes whole video as input: ~15,780 tokens for 60s (rate varies ~100–300 tokens/sec with
  resolution — treat costs as order-of-magnitude). At $0.30/1M (2.5 Flash) that's **~$0.005–0.02 per video**;
  1,000 videos/month ≈ $5. Best default for Hebrew. ([pricing](https://ai.google.dev/gemini-api/docs/pricing))
- **Twelve Labs Pegasus does not support Hebrew** (12 partial languages, Hebrew absent) — ruled out for speech.
  **Marengo** (embeddings/search) *does* support Hebrew since 3.0 and costs $0.042/min indexing + $4/1k queries —
  the eventual route for "find videos like mine," deferred until the cheap version proves insufficient.
- **Hebrew ASR is free**: [ivrit-ai/whisper-large-v3](https://huggingface.co/ivrit-ai/whisper-large-v3), Apache-2.0,
  self-hostable. Language token must be set explicitly to Hebrew.

### Creation
- **Remotion is free for us** — individuals and teams up to 3 people, unlimited commercial renders. Paid tiers
  ($100/mo Automators) only bite at 4+ employees. ([license](https://remotion.pro/license))
- **Creatomate $54/mo** = 2,000 credits ≈ 550+ short videos — the no-infrastructure escape hatch.
- **Veo 3.1 is the budget-eater**: $0.40/sec standard (~$3.20 per 8s clip), Fast $0.10–0.30/sec, Lite $0.05–0.08/sec.
  $50–200/mo buys only ~15–60 standard clips. Use Fast/Lite; reserve standard for hero shots.
- **Hebrew voice**: ElevenLabs supports Hebrew **only on Eleven v3** (from $6/mo Starter; free tier has no commercial
  license). **ElevenLabs Professional Voice Cloning does NOT cover Hebrew** — officially refuted this round.
  **MiniMax** is the best-evidenced route to Erez's own cloned voice in Hebrew (~$1.5/clone, 10s–5min sample),
  with Hebrew quality verified only by [third-party hands-on testing](https://github.com/danielrosehill/Hebrew-TTS-Providers)
  — **we must run our own test with his voice before promising it.**

### Engagement
- **Instagram comment automation is fully supported** on his own professional account: get/reply/delete/hide/disable,
  with webhooks. Needs `instagram_manage_comments`. ([Meta](https://developers.facebook.com/docs/instagram-platform/overview/))
- **Instagram DMs**: auto-reply allowed only inside a **24-hour window** from his user's message. The `human_agent`
  tag extends to 7 days but requires App Review and **may only be used for genuine human responses — bots using it
  is a policy violation.**
- **TikTok has no organic comment/DM API.** Research API is read-only; the Business API's reply endpoint covers ads
  only. TikTok is **read/notify-only** for engagement. Do not automate it.
- App Review is **not** fully avoidable even for his own account (a claim that it was got refuted 3-0).

### Interface (WhatsApp)
- **A WhatsApp template body is capped at 1024 characters, hydrated** — passing the digest as a variable fails with
  error 132005. **The digest cannot live in the message.** The supported pattern is a short template + a URL button
  (1 variable, appended to end). → **A web digest page is a phase-1 necessity, not a later dashboard.**
- **The 07:00 digest must be a pre-approved utility template.** Free-form messages work only inside an open 24-hour
  customer service window, which opens/resets on each inbound message from Erez.
- **Cost is a non-issue**: ~$1–2/month for one recipient (Twilio adds $0.005/message). Israel is bucketed under
  "Other countries" ($0.0008–$0.0550 band); its exact rate publishes before 2026-09-01.
- **Friction is the real cost**: dedicated phone number (a number already on WhatsApp cannot be registered — Erez
  needs a second SIM or voice-OTP-capable VoIP), Meta Business verification, template approval.
- ⚠️ **2026-10-01: free-form service messages start billing per message**, no volume tiers. Our ad-hoc Hebrew chat
  replies are service messages.
- **Unofficial libraries (Baileys/whatsapp-web.js) are rejected**: maintainers disclaim all liability; a ban is
  Erez's personal number, permanently, with zero recourse.

### Publishing
- **Instagram: works.** Content Publishing API supports REELS/STORIES/CAROUSEL via the container flow, **100 posts
  per 24h**. Gotcha: Page Publishing Authorization blocks publishing with no programmatic way to detect it.
- **YouTube: works.** 100 uploads/day in a dedicated quota bucket (upload cost dropped ~1600→~100 units in Dec 2025).
- **TikTok is the wall.** Unaudited clients are forced to `SELF_ONLY` visibility, 5 posting users/24h, accounts private
  at posting. Lifting it needs a **2–6 week UX-compliance audit that explicitly rejects apps resembling side projects.**
  → **TikTok stays draft-and-tap-publish.**

### Rejected
- **OpenClaw** (~383k stars, MIT, self-hosted chat assistant): matches the interaction model but has documented
  plaintext credential leaks, prompt-injection theft via its messaging integrations, ~135k publicly exposed instances
  with plaintext keys (SecurityScorecard), and 7.1% of its skill registry leaking credentials (Snyk). Handing a
  non-technical creator an agent with shell access holding Meta tokens, while it reads untrusted inbound DMs, is
  exactly the threat model we must avoid.
- **"HermesClaw"** is a WeChat multiplexer, not an orchestration framework. Irrelevant.
- **n8n / Make / Zapier**: n8n needs an engineer to operate (fine for Elik, useless for the handoff); Make/Zapier
  can't host the Hebrew prompt logic that is Erez's learning surface. A small Python codebase teaches more.

### Still unresearched (honest gaps)
These produced **no verified claims** and must not be read as "no issues found":
1. **AI-content disclosure policies** (Meta AI-info labels, TikTok C2PA auto-labeling, YouTube synthetic-content
   disclosure; whether Veo/Sora outputs carry auto-detected metadata; political/advocacy content rules).
   **Blocks phase 4.** Must be researched before the advocacy channel is built.
2. **Draft-approve tooling** — whether ManyChat/Chatfuel can do human-in-the-loop at all (doubtful; they are
   flow-based auto-responders). Blocks the phase-3 buy-vs-build call.
3. **Creator-monitoring economics** — units/cost for watching ~20 accounts daily. Resolved by a **week-1 measurement
   spike**, not more web research.

---

## 4. The design

**Chassis: "Sadna" (הסדנה — the workshop)** — chosen by two independent adversarial judges over an MVP-first and a
platform-first alternative, and independently confirmed by Erez's own #1 goal being *learning*.

### Principle

> One boring Python process that a beginner can hold in his head, where Erez's first "deploys" are Hebrew prompt
> files, and where he cannot break production or leak a secret even if he tries.

### Architecture

One Python 3.12 process on Railway. One SQLite file. No queues, no microservices, no Postgres, no vector DB, no
Kubernetes. Three external APIs at first (Gemini, Claude, one data vendor) plus the notifier — and Erez never
handles a key, since prod secrets live only in Railway.

```
07:00 Asia/Jerusalem
  scheduler
    → collectors/       watchlist creators + topics  ──┐
        youtube.py      (official API, free)           │  logged-out public data only
        ensembledata.py (IG + TikTok)                  │  NEVER Erez's account
        apify_*.py      (fallback, week-1 spike)     ──┘
    → store/db.py       dedupe vs SQLite (never re-analyze the same video)
    → digest/rank.py    velocity score (views/hour since post)
    → analyze/fetch.py  yt-dlp download  (+ Telegram file-upload fallback)
    → analyze/gemini.py whole-video → structured JSON, rubric from prompts/analysis_rubric.md
    → digest/build.py   Hebrew prose (Claude) from prompts/digest.md
    → digest/page.py    render the web digest page
    → notify/           Telegram now → WhatsApp later (teaser template + URL button)
  07:30 dead-man's-switch → alert Elik if no digest went out

On demand (any time)
  Erez sends a Reel URL or uploads a video in chat
    → same fetch → Gemini → Hebrew analysis reply
    → stored, so every question compounds the corpus
```

**Two LLMs, each with one reason:**
- **Gemini Flash** — video analysis. It is the only cheap model that ingests whole video, and it handles Hebrew.
- **Claude** — Hebrew digest prose and chat. Both judges independently flagged *"bland Hebrew prose is why Erez stops
  reading"* as the top threat to criterion (a). ~$10/mo is cheap insurance on the one artifact he must want to open.

### Repo layout

Every file under ~150 lines, one purpose each.

```
CLAUDE.md              rules for AI pairing, bilingual — the guardrails Erez's Claude obeys
Makefile               make setup | make test | make digest-preview
prompts/*.md           EREZ OWNS: digest.md, analysis_rubric.md, bot_persona.md, ideas.md
config/*.yaml          EREZ OWNS: watchlist.yaml (his favorite creators), topics.yaml
app/
  bot.py               chat interface
  scheduler.py         APScheduler
  collectors/          base.py + one file per source  ← the vendor seam, swappable in one file
  analyze/             fetch.py, gemini.py
  digest/              rank.py, build.py, page.py
  notify/              base.py, telegram.py, (whatsapp.py later)  ← the interface seam
  store/db.py          SQLite: videos, analyses, digests, provider_usage
web/                   the digest page
tests/ + fixtures/     golden files; offline, zero API keys
docs/learn/            numbered 5-minute Hebrew lessons, mapped to the module each task touches
```

### Security doctrine (written into CLAUDE.md now, inherited by phase 3)

- Inbound comments/DMs are **untrusted data**. No tool-use over raw comment text. One constrained drafting call,
  allowlisted actions only, draft-approve via chat buttons.
- **Prod secrets never on Erez's machine.** He gets a dev bot token and a spend-capped Gemini key.
- `gitleaks` in CI. Branch protection on `main`. CLAUDE.md forbids his assistant from touching `collectors/`,
  `.github/`, or anything secret-adjacent without Elik.
- No scraping through Erez's account, ever. Logged-out public data only.

### Cost control

`provider_usage` table records every vendor call; a `/costs` command surfaces spend **in chat, before the bill**.
Hard per-vendor caps.

---

## 5. Phases

### Phase 1 — the first win (weeks 1–4)
| Week | Deliverable |
|---|---|
| 1 | Repo skeleton + CLAUDE.md. Telegram echo bot live on Railway. YouTube API key (free). **Vendor spike: EnsembleData trial vs Apify — measure real units/day.** Start Meta Business verification + WhatsApp number (long lead time). |
| 2 | **`/analyze` ships first** — Erez sends a URL or uploads a video, gets Hebrew analysis. Zero vendor dependency, maximum delight. |
| 3 | **Digest v1** — his watchlist creators + topics → collect → rank → analyze → Hebrew digest → web page → 07:00 ping. Dead-man's-switch at 07:30. |
| 4 | Tuning with Erez. **His first commit: `watchlist.yaml` via the GitHub web UI** — merged, deployed, visible in tomorrow's digest. Decide the EnsembleData tier from measured usage. |

**Exit:** Erez reads the digest daily and has analyzed 3+ videos. Criteria (a) and (b) met.

### Phase 2 — Erez onboards, analysis deepens (weeks 5–8)
- **Style notes**: one-time Gemini pass over his own top reels + the creators he admires → a markdown style profile.
  Powers a *"why this fits your world"* digest section. (Cheap; Marengo embeddings only if this proves insufficient.)
- **`/ideas`**: hooks, purple cows, Israeli-audience adaptation — his stated want, pure prompts.
- **WhatsApp switchover** when the paperwork clears: teaser template + link to the web digest.
- **Erez**: `make setup`, dev bot, 2–3 good-first-issues sized to one Claude Code session each, as reviewed PRs.
- Bot posts a Hebrew changelog crediting each merged PR — *"עדכון חדש מארז"*.

**Exit:** one Erez PR merged without Elik writing code. **Criterion (c) met.**

### Phase 3 — creation + engagement drafts (weeks 9–16)
- **Remotion engine** (Elik-owned) driven by **JSON templates Erez edits**: carousels, captions, AI additions to his
  real footage.
- **MiniMax Hebrew voice-clone test** (~$1.5) — he consented; verify quality before promising anything.
- **IG comment/DM draft-approve**: webhook → Claude drafts in his voice → he approves in chat → send.
  Untrusted-input doctrine applies. **TikTok: notify-only.** Start Meta App Review early.
- **Auto-publishing**: Instagram + YouTube programmatic; **TikTok draft-and-tap**.

### Phase 4 — the global AI channel (months 5+)
- **Separate account. AI disclosure on by default.** Protects the authentic Hebrew brand that currently works;
  AI + political content is the highest-scrutiny combination on every platform.
- Veo Fast/Lite under a hard monthly cap.
- **Gated on the AI-disclosure research** (§3, gap 1) being completed first.

---

## 6. Cost model

| | Month 1 | Steady (2–4) | Phase 3 |
|---|---|---|---|
| Data vendor | $0 (trial) | $100 EnsembleData *(or ~$49 Apify if the spike wins)* | same |
| Gemini Flash | ~$5 | $5–10 | $5–10 |
| Claude API | ~$5 | ~$10 | ~$10 |
| Railway | $5–10 | $5–10 | $5–10 |
| Claude Pro (Erez's learning tool) | $20 | $20 | $20 |
| ElevenLabs / MiniMax | — | — | $6–27 |
| Veo (hard cap) | — | — | ≤$20 |
| **Total** | **~$35–40** | **~$140–150** *(~$90–100 on Apify)* | **~$170–190** |

Inside the $50–200 envelope on every path. The only lever that busts it is EnsembleData's $200 tier — mitigated by
caching searches in SQLite, capping daily queries, and the week-1 spike.

---

## 7. How Erez becomes a builder

A ladder where **every rung gives real production impact before it demands new skills**.

| Rung | When | What he does | Safety net |
|---|---|---|---|
| 0 | wk 1–3 | Uses the bot. Digest footer links to `docs/learn/`. | — |
| 1 | wk 4–5 | **Owns `prompts/*.md` and `config/watchlist.yaml`** — Hebrew text and his creator list. Edits via GitHub web UI or Claude Code, opens a PR, Elik approves, tomorrow's digest changes. A real deploy loop learned on files that cannot crash anything. | Text-only; CI |
| 2 | wk 5–10 | **Guided coder.** `make setup` = working env in one command. `make digest-preview` renders from fixtures with **zero API keys** — an unbreakable sandbox. Picks from Elik's good-first-issue list, one Claude Code session each. | Dev bot cannot message the real chat; no prod secrets on his machine; CI + one-click Railway rollback |
| 3 | wk 10+ | **Feature owner.** Ships `/ideas` end-to-end. Elik reviews only. | Branch protection; gitleaks |

CLAUDE.md instructs his assistant to explain every change **in Hebrew**, keep functions under 30 lines, always run
`make test`, and refuse to touch secret-adjacent paths without Elik.

---

## 8. Risks

| Risk | Mitigation |
|---|---|
| **Bland Hebrew digest → he stops reading** (kills criterion a) | Claude writes the prose, not Flash. Erez owns `prompts/digest.md` from week 4 and tunes his own voice. |
| **Scraper vendor breaks or prices out** | Vendor seam is exactly one file. Week-1 spike validates a fallback before we depend on it. YouTube (free, official) always works. |
| **yt-dlp blocked / IP-banned** | Telegram file-upload path (note: 20MB `getFile` cap — larger reels need the URL path). Pre-priced ~$10 residential proxy. Digest degrades to metadata-only rather than failing silently. |
| **WhatsApp paperwork delays month 1** | Telegram bridge ships week 2; notifier is a swappable module; paperwork runs in parallel. |
| **Oct 1 2026 WhatsApp service-message billing** | Volume is ~30 messages/month — cost stays noise. Re-check Israel's rate when published (before 2026-09-01). |
| **Erez never climbs the ladder** | Rung 1 requires zero code and pays off in 24h. If he stalls there, the product still delivers (a) and (b); we learn the truth in week 5, not month 6. |
| **AI + advocacy content gets throttled or removed** | Separate account, disclosure by default, research gate before building. Never mixed into the feel-good brand. |
| **Meta App Review rejection (phase 3)** | Start review one phase early. Fallback: notify-only engagement, which still saves him time. |
| **Erez's account banned** | Never scrape with his account. Official APIs only for anything touching his profile. No unofficial WhatsApp libraries. |

---

## 9. Decisions made

1. **Chassis**: Sadna hybrid — learning-first, with One-Bot sequencing (`/analyze` before digest, dead-man's-switch,
   week-1 spike) and Masad grafts (free YouTube API, `provider_usage` + `/costs`, untrusted-input doctrine,
   store-every-analysis).
   *Rejected*: hot-reload-from-`main` (adds a GitHub dependency to the 07:00 critical path) → plain merge-triggers-redeploy.
2. **Interface**: Telegram bridge → WhatsApp when approved. Web digest page from phase 1 (forced by the 1024-char cap,
   and better anyway).
3. **Advocacy channel**: separate account, phase 4, disclosure on by default, gated on research.

## 10. Open questions

1. AI-disclosure + political-content policies — **research before phase 4**.
2. Draft-approve tooling (ManyChat vs custom) — **decide at phase 3**.
3. Creator-monitoring unit economics — **week-1 spike**.
4. Does Erez have a spare phone number for WhatsApp, or do we buy a VoIP number?
5. MiniMax Hebrew clone quality with *his* voice — **hands-on test at phase 3**.
