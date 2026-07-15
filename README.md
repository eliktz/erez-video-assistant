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
