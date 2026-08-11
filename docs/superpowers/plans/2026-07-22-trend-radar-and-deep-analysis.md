# Trend Radar + Deep Video Analysis — Action Plan

**For Elik.** Erez split a broad ask (2026-07-22) into three tracks. This is what's already
done (no code needed), what's ready to build without a decision, and what needs Elik +
a budget call.

**Track 1 — general trend radar.** Every 07:00, a signal of what's generally trending
across networks — a song, a challenge, anything blowing up — independent of whether it's
emotional. Start on YouTube Shorts now; expand (paid) to Instagram, TikTok, Facebook.
Facebook specifically: Erez's personal page is his strongest channel, ~100K followers.

**Track 1's final shape is a 2×2, not one list** (Erez, 2026-07-24): every trending item
gets sorted into one of four buckets before it reaches the digest —

|              | Emotional/viral-kindness genre | Regular/general trending |
|--------------|--------------------------------|---------------------------|
| **Israel**   | quadrant A — **3/day**          | quadrant B — **2/day**    |
| **World**    | quadrant C — **3/day**          | quadrant D — **2/day**    |

Counts fixed by Erez (2026-07-25): 3 + 3 + 2 + 2 = **10 items/day total**, which matches
`settings.yaml`'s existing `digest.max_videos: 10` — no cost-cap surprise, just re-allocating
the same 10 slots across the four quadrants instead of one undifferentiated top-10.

"Emotional" here means: does it match Erez's genre (kindness, social experiment, staged
street moment) — run it through the Track 2 rubric to decide. "Regular" is everything else
trending (a song, a meme, a news story, a challenge with no emotional angle). Quadrants A/C
feed Track 2's deep analysis and Track 3's `/idea`; B/D are shown as a lighter "here's what's
generally buzzing" list, since Track 2's rubric doesn't apply to a non-emotional trend.

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
      chart, not a keyword search. **Two separate pulls, not one merged list** (Erez,
      2026-07-23, refining the 2026-07-23 "make it global" note): call it once with
      `regionCode=IL` and once with no region filter (or a few major regions — US, UK —
      merged), and show them as **two distinct sections** in the digest, not blended
      together. Reason: Israel's chart is what's locally relevant right now (local news,
      local audio, timing); the global chart is what's inspiration-worthy from worldwide
      creators (andr3w_wave, Dhar Mann, KINDNESS MAN are all non-Israeli) — mixing them
      would bury one signal inside the other. New collector function; touches
      `app/collect/youtube.py` (restricted — Elik) plus a new digest section (or two) so
      trend-radar items don't get mixed into the emotional-video writeup either
      (`app/digest/rank.py`, `compose.py`, `jobs.py`, `prompts/digest.md`).
- [ ] **Classify each trending item into the 2×2 (see above).** Run it through the same
      rubric call Track 2 already uses (`gemini.analyze_video`) to decide emotional-genre
      vs regular — `fits_erez_style` (already in the rubric) is most of this decision
      already. No new AI call type needed, just routing: emotional → Track 2/3 pipeline,
      regular → a lighter trend-list section with no deep analysis.
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

## Track 4: creator discovery — needs Elik, new collector code

Erez (2026-07-25): he wants the bot to keep **finding new creators** in the style of the
ones already in `config/watchlist.yaml`, not just track the ~15 he's manually added so
far. The tracked creators are meant as **reference examples of a style/audience**, not an
exhaustive list — the bot should use them to go find more like them.

- [ ] **How this actually works today (manually, in chat):** search YouTube for the
      hashtags Erez's tracked creators use in their captions (`#lovely #kindness`,
      `#actsofkindness`, etc.), sorted by view count, then check each result channel's
      subscriber count and current activity before it's worth adding. This is exactly how
      andr3w_wave, KINDNESS MAN, THE GREAT HERO, Dhar Mann, Coby Persin, Bufones.net were
      found this week — by hand, one search at a time.
- [ ] **To make the bot do this itself:** a new collector function in
      `app/collect/youtube.py` (restricted — Elik) that takes the hashtags already seen in
      tracked creators' captions (or a small curated list in `config/watchlist.yaml`, e.g.
      a new `discovery_hashtags` field) and runs `search.list` against them, same pattern
      as `_search_topic`. Needs a **channel-level** result too (not just video-level) —
      YouTube's `search.list` with `type=channel` returns channels directly.
- [ ] **Keep the human in the loop.** New channels should not silently join the tracked
      list and start feeding the digest — every creator added this week went through Erez
      approving each one by name in chat first. Cheapest version: a new digest section or
      a `/discover` command that surfaces 3-5 candidate channels (name, subscriber count,
      one standout video) for Erez to approve, same as the manual process now, just
      run by the bot instead of by hand.
- [ ] **No vendor needed for the YouTube side** — this uses the same free YouTube Data API
      already in use. Instagram/TikTok creator discovery has the same vendor dependency as
      Track 1's Instagram/TikTok trending (the spike below).

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
5. **Cheap, no vendor, but a real code project:** Track 4 creator discovery on YouTube —
   lower priority than Track 1's quadrants, since manual discovery in chat works fine as a
   stopgap and costs nothing but Erez's/Claude's time.
