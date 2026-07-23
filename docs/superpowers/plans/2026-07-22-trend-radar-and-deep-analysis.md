# Trend Radar + Deep Video Analysis — Action Plan

**For Elik.** Erez split a broad ask (2026-07-22) into three tracks. This is what's already
done (no code needed), what's ready to build without a decision, and what needs Elik +
a budget call.

**Track 1 — general trend radar.** Every 07:00, a signal of what's generally trending
across networks — a song, a challenge, anything blowing up — independent of whether it's
emotional. Start on YouTube Shorts now; expand (paid) to Instagram, TikTok, Facebook.
Facebook specifically: Erez's personal page is his strongest channel, ~100K followers.

**Track 2 — deep analysis of emotional videos.** Why a video is trending, why it's
emotional, why it has so many views. Applies to both auto-discovered videos in the daily
digest and videos Erez sends on demand, against a rubric he tunes over time: retention
(what keeps someone watching to the end, not just the hook), drop-off point, "purple cow"
novelty, call-to-action quality.

**Track 3 — idea generation.** Erez said it plainly (2026-07-23): once the bot knows what's
trending and why it worked, it should help him turn that into concrete video ideas for his
own audience — more Israeli, more Zionist — and pitch new creative concepts, not just
analyze other people's videos. This is the `/idea` command already scoped in
`docs/good-first-issues.md` #4 ("the big one").

---

## Already done — no Elik needed

Both of these are `prompts/*.md` / `config/*.yaml`, which are Erez-owned and not
restricted. Done 2026-07-22:

- [x] `prompts/analysis_rubric.md` now asks for `retention`, `drop_off_risk`,
      `purple_cow`, `cta`, and `fits_which_page` (erez / gentleman / both / none).
      Because on-demand link analysis and the daily digest both call
      `app/analyze/gemini.py::analyze_video` with this same rubric, **this covers Track 2
      for both paths already** — no code change was needed for the analysis depth itself.
- [x] `config/watchlist.yaml` topics widened. Correction from Erez (2026-07-23): the
      *search* itself should stay broad — emotional/viral content in general (kindness,
      social experiments, random gifts/flowers to strangers), not narrowed to
      soldiers/Zionist terms. The Israeli/Zionist angle is applied later, at the idea stage
      (Track 3), not at discovery. Both broad and narrow topics are in the file now. Still
      keyword search, not a trend chart — see Track 1 below for the gap that leaves open.

## Ready to build without a decision (not in the restricted-files list)

- [ ] **Video file upload fallback** — `docs/follow-ups.md` #4. Erez wants to send a video
      directly (not just a link) for analysis with tunable parameters. Link analysis exists;
      raw upload doesn't. `app/bot.py` already tells users to send the file when a download
      fails, but no handler exists for it. Needs a
      `MessageHandler(filters.VIDEO | filters.Document.VIDEO, ...)` in `app/main.py` that
      pulls the file via Telegram `getFile` and runs it through the same
      `gemini.analyze_video` path. None of the touched files (`app/main.py`, `app/bot.py`,
      `app/analyze/fetch.py`) are in the "don't touch without Elik" list — this can be
      built on request without waiting on this plan.
- [ ] **Track 3: `/idea` command.** Already scoped in `docs/good-first-issues.md` #4: a new
      `prompts/ideas.md` (Erez-owned, no code) plus a `CommandHandler("idea", ...)` in
      `app/main.py`. It reads the last N analyzed videos from the DB (already stored —
      `app/store/videos.py`), and asks Gemini to pitch 3 concrete video ideas for Erez,
      translated to his Israeli/Zionist audience and tagged to whichever of his two pages
      (`fits_which_page`, already in the rubric) they suit. No new collector, no vendor, no
      Elik — this is buildable today on the existing data the bot already has.
      **Not a one-shot output** (Erez, 2026-07-23): `/idea` should read as a brainstorm
      opener, not a final answer — he replies in chat ("develop idea 2", "make that one
      for Gentleman instead") and the bot keeps refining with him. Uses the existing
      free-form chat/reply path, not a new mechanism.

## Track 1: general trend radar — needs Elik, new collector code

The current YouTube collector (`app/collect/youtube.py`, restricted) only does keyword
search ranked by most-viewed-in-48h per topic. There's no notion of "trending independent
of topic" — a trending song or challenge with no kindness/soldier angle wouldn't surface
today even on YouTube.

- [ ] **YouTube trending chart (free, no vendor).** `videos.list(chart=mostPopular)` is a
      different endpoint than the search call used today — it's YouTube's own trending
      chart, not a keyword search. **Global, not `regionCode=IL`** (Erez, 2026-07-23): his
      inspiration sources are worldwide creators (andr3w_wave, Dhar Mann, KINDNESS MAN are
      all non-Israeli), so scoping this to Israel-only would miss exactly the content this
      track exists to surface. Query without a region filter (or loop a few major regions —
      US, UK, etc. — and merge), not `regionCode=IL`. New collector function; touches
      `app/collect/youtube.py` (restricted — Elik) plus a new digest section so trend-radar
      items don't get mixed into the emotional-video writeup (`app/digest/rank.py`,
      `compose.py`, `jobs.py`, `prompts/digest.md`).
- [ ] **Flag, don't build yet: trending *audio/song* detection has no YouTube API
      equivalent.** YouTube doesn't expose a "trending sounds" endpoint — that's native to
      TikTok/Instagram's own discovery, not YouTube Shorts. Realistically this piece only
      becomes possible once the IG/TikTok vendor (below) is in.
- [ ] **Instagram + TikTok — run the vendor spike** that's been pending since phase 1
      (`docs/follow-ups.md`, Task 9 Step 1/6). Budget: $49–100/mo (EnsembleData-class).
      When evaluating, check specifically for a *trending-content* endpoint, not just
      per-profile scraping — Track 1 needs "what's trending," Track 2 needs "what did this
      creator post."
- [ ] **Facebook — this is two different asks, don't conflate them:**
      1. **Erez's own page** (100K followers) — easy and free: Graph API + a Page Access
         Token Erez generates himself. He owns the page, so this needs no personal login/
         cookies and doesn't touch the "never scrape with Erez's account" rule — a Page
         token is Meta's sanctioned mechanism for a page's own owner. Gets his own post
         performance (reach, engagement) — useful for "what already works for him," not
         for discovering outside trends.
      2. **"What's trending on Facebook generally"** — Facebook has no public API for this
         (no equivalent to YouTube's trending chart). Getting it needs the same kind of
         paid vendor as IG/TikTok, if one even covers Facebook video trends — check during
         the same spike above.

## Decision Elik + Erez need to make

1. Ship Track 1 in stages — YouTube trending chart first (free, this week), paid vendors
   later — or wait for full budget approval before building any of it?
2. Approve the vendor spike and budget ($49–100/mo) for Instagram/TikTok, and check Facebook
   trend coverage in the same evaluation.
3. Decide whether Erez's own Facebook Page Graph API connection (free, separate from
   trend-radar spend) is worth doing now given how strong that page already is.

## Priority order (recommended)

1. **Now, free:** rubric deepening (done), watchlist tuning (done), video-upload fallback
   (buildable today), `/idea` command (buildable today — Track 3, this is what actually
   closes the loop Erez asked for: trend → why it worked → an idea for his own channel).
2. **Cheap, no vendor:** YouTube trending-chart collector + digest section split.
3. **Free but separate value:** Erez's own Facebook Page via Graph API — personal
   analytics, not trend discovery.
4. **Needs budget + a decision:** Instagram + TikTok + general Facebook trending, one
   vendor spike covering all three.
