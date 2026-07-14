"""Entrypoint: one process, bot + scheduler. Run with `make run`."""

import logging
from datetime import UTC

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from app import bot, config, jobs
from app.analyze import gemini
from app.collect.youtube import YouTubeSource
from app.digest import compose
from app.notify.telegram import TelegramNotifier
from app.store import db

logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s %(message)s", level=logging.INFO)
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


async def on_costs(update: Update, ctx) -> None:
    from datetime import datetime

    month = datetime.now(UTC).strftime("%Y-%m")
    await update.message.reply_text(bot.costs_message(ctx.bot_data["deps"].conn, month=month))


async def on_message(update: Update, ctx) -> None:
    match = bot.URL_RE.search(update.message.text or "")
    if not match:
        await update.message.reply_text("שלח לי לינק לסרטון ואני אנתח אותו.")
        return
    await update.message.reply_text("רגע, מנתח... 🎬")
    reply = bot.analyze_url(match.group(0), deps=ctx.bot_data["deps"])
    await update.message.reply_text(reply)


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
        CronTrigger(hour=settings["digest"]["hour"], minute=settings["digest"]["deadman_minute"]),
        id="deadman",
    )
    scheduler.start()
    log.info("Scheduler started: digest at %02d:00 Asia/Jerusalem", settings["digest"]["hour"])


def main() -> None:
    app = Application.builder().token(config.env("TELEGRAM_BOT_TOKEN")).build()
    app.bot_data["deps"] = build_deps()
    app.add_handler(CommandHandler("start", on_start))
    app.add_handler(CommandHandler("costs", on_costs))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    log.info("Bot starting (long polling)")
    start_scheduler(app.bot_data["deps"])
    app.run_polling()


if __name__ == "__main__":
    main()
