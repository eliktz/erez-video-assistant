"""Entrypoint: one process, bot + scheduler. Run with `make run`."""

import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from app import bot, config
from app.analyze import gemini
from app.digest import compose
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
