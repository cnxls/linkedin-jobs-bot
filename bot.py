from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    ConversationHandler,
)

from db import JobsDB
from scraper import search_jobs
from formatter import format_digest

WAITING_KEYWORDS = 1


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "LinkedIn Jobs Bot\n\n"
        "/check — Search for jobs now\n"
        "/keywords — View/update search keywords"
    )


async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Searching for jobs...")

    cfg = context.bot_data
    db = cfg["db"]
    keywords = db.get_keywords() or cfg["default_keywords"]
    all_jobs = search_jobs(cfg["apify_token"], keywords, cfg["location"], cfg["experience_level"])

    new_jobs = []
    for job in all_jobs:
        if not db.is_seen(job["id"]):
            new_jobs.append(job)
            db.mark_seen(job["id"])

    message = format_digest(new_jobs)
    await update.message.reply_text(message)


async def keywords_show(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = context.bot_data
    db = cfg["db"]
    current = db.get_keywords() or cfg["default_keywords"]
    text = "Current keywords:\n"
    for kw in current:
        text += f"  - {kw}\n"
    text += "\nSend new keywords (comma-separated) or /cancel:"
    await update.message.reply_text(text)
    return WAITING_KEYWORDS


async def keywords_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text
    new_keywords = [kw.strip() for kw in raw.split(",") if kw.strip()]
    if not new_keywords:
        await update.message.reply_text("No valid keywords. Try again or /cancel.")
        return WAITING_KEYWORDS

    db = context.bot_data["db"]
    db.set_keywords(new_keywords)
    await update.message.reply_text(
        "Updated keywords to:\n" + "\n".join(f"  - {kw}" for kw in new_keywords)
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END


def main():
    from config import (
        APIFY_TOKEN,
        TELEGRAM_TOKEN,
        DB_PATH,
        DEFAULT_KEYWORDS,
        DEFAULT_LOCATION,
        DEFAULT_EXPERIENCE_LEVEL,
    )

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.bot_data["db"] = JobsDB(DB_PATH)
    app.bot_data["apify_token"] = APIFY_TOKEN
    app.bot_data["default_keywords"] = DEFAULT_KEYWORDS
    app.bot_data["location"] = DEFAULT_LOCATION
    app.bot_data["experience_level"] = DEFAULT_EXPERIENCE_LEVEL

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("check", check))

    keywords_handler = ConversationHandler(
        entry_points=[CommandHandler("keywords", keywords_show)],
        states={
            WAITING_KEYWORDS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, keywords_update)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(keywords_handler)

    print("Bot is running. Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()
