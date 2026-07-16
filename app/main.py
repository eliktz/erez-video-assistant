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

# httpx logs every request URL at INFO — and our secrets live IN those URLs: the Telegram
# token as a path segment (.../bot<TOKEN>/sendMessage) and the YouTube key as ?key=<KEY>.
# At INFO they would be written to Railway's logs in cleartext, undoing "secrets only in env".
logging.getLogger("httpx").setLevel(logging.WARNING)

# The digest promise is "07:00 Erez's time". APScheduler only applies the scheduler's timezone
# to triggers it builds itself; a CronTrigger constructed here would default to the machine's
# local zone (UTC on Railway -> 10:00 in Israel). So every trigger names the zone explicitly.
TZ = "Asia/Jerusalem"


def build_deps() -> bot.Deps:
    return bot.Deps(
        conn=db.connect(config.env("DB_PATH", "data/erez.db")),
        gemini_client=gemini.build_client(config.env("GEMINI_API_KEY")),
        rubric=config.load_prompt("analysis_rubric"),
        persona=config.load_prompt("bot_persona"),
        work_dir="/tmp/erez-videos",
        monthly_cap_usd=config.load_settings()["cost"]["monthly_cap_usd"],
    )


def allowed_chat_ids() -> set[int]:
    """The only chats the bot answers: Erez, and Elik for admin."""
    return {
        int(config.env("TELEGRAM_CHAT_ID_EREZ")),
        int(config.env("TELEGRAM_CHAT_ID_ADMIN")),
    }


def _authorized(update: Update, ctx) -> bool:
    """Deny before doing any paid work. Silent: a stranger gets no reply at all."""
    chat = update.effective_chat
    if chat is not None and bot.is_authorized(chat.id, ctx.bot_data["allowed_chat_ids"]):
        return True
    log.warning("Ignoring update from unauthorized chat %s", chat.id if chat else "unknown")
    return False


async def on_start(update: Update, ctx) -> None:
    if not _authorized(update, ctx):
        return
    await update.message.reply_text(
        "היי ארז 👋\nשלח לי לינק לרילס/טיקטוק/שורטס ואני אנתח לך אותו.\n"
        "כל בוקר ב-7:00 תקבל ממני דוח טרנדים."
    )


async def on_costs(update: Update, ctx) -> None:
    from datetime import datetime

    if not _authorized(update, ctx):
        return
    month = datetime.now(UTC).strftime("%Y-%m")
    await update.message.reply_text(bot.costs_message(ctx.bot_data["deps"].conn, month=month))


async def on_message(update: Update, ctx) -> None:
    if not _authorized(update, ctx):
        return
    match = bot.URL_RE.search(update.message.text or "")
    if not match:
        # In the group, Erez and Elik also just talk. Only nag for a link in a private
        # chat; in a group, stay silent unless there is actually a URL to analyze.
        if update.effective_chat.type == "private":
            await update.message.reply_text("שלח לי לינק לסרטון ואני אנתח אותו.")
        return
    await update.message.reply_text("רגע, מנתח... 🎬")
    try:
        reply = bot.analyze_url(match.group(0), deps=ctx.bot_data["deps"])
    except Exception:
        # A failed analysis must never end in silence — say so and ask to retry.
        log.exception("analyze_url failed for %s", match.group(0))
        reply = "משהו נתקע אצל ספק ה-AI (עומס זמני אצלם). נסה לשלוח שוב עוד דקה 🙏"
    await update.message.reply_text(reply)


def start_scheduler(deps: bot.Deps) -> None:
    """APScheduler in-process: no cron, no second system to learn."""
    settings = config.load_settings()
    if not settings["digest"].get("enabled", False):
        # No real video source yet, so the digest would just say "found nothing" every
        # morning. Stay on-demand-only until settings.yaml flips digest.enabled to true.
        log.info("Daily digest disabled (settings.yaml digest.enabled=false) — on-demand only.")
        return
    token = config.env("TELEGRAM_BOT_TOKEN")
    erez = TelegramNotifier(token, config.env("TELEGRAM_CHAT_ID_EREZ"))
    admin = TelegramNotifier(token, config.env("TELEGRAM_CHAT_ID_ADMIN"))
    sources = [YouTubeSource(config.env("YOUTUBE_API_KEY"))]

    scheduler = BackgroundScheduler(timezone=TZ)

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
        CronTrigger(
            hour=settings["digest"]["hour"], minute=settings["digest"]["minute"], timezone=TZ
        ),
        id="daily_digest",
    )
    scheduler.add_job(
        _deadman_job,
        CronTrigger(
            hour=settings["digest"]["hour"],
            minute=settings["digest"]["deadman_minute"],
            timezone=TZ,
        ),
        id="deadman",
    )
    scheduler.start()
    log.info("Scheduler started: digest at %02d:00 %s", settings["digest"]["hour"], TZ)


async def on_error(update, ctx) -> None:
    """Log anything a handler raises, so failures are diagnosable instead of silent."""
    log.error("Unhandled error while processing an update", exc_info=ctx.error)


def main() -> None:
    app = Application.builder().token(config.env("TELEGRAM_BOT_TOKEN")).build()
    app.bot_data["deps"] = build_deps()
    allowed = allowed_chat_ids()
    app.bot_data["allowed_chat_ids"] = allowed

    # Gate every handler at registration AND again inside each callback (_authorized).
    # Either alone would do; both means a new handler cannot silently be left open.
    only_us = filters.Chat(chat_id=allowed)
    app.add_handler(CommandHandler("start", on_start, filters=only_us))
    app.add_handler(CommandHandler("costs", on_costs, filters=only_us))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & only_us, on_message))
    app.add_error_handler(on_error)
    log.info("Bot starting (long polling); answering %d authorized chat(s)", len(allowed))
    start_scheduler(app.bot_data["deps"])
    app.run_polling()


if __name__ == "__main__":
    main()
