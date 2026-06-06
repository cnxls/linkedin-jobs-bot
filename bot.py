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
from formatter import format_digest_chunks

WAITING_KEYWORDS = 1
WAITING_INTERVAL = 2


def _get_chat_id(update: Update) -> str:
    return str(update.effective_chat.id)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "LinkedIn Jobs Bot\n\n"
        "/check — Search for jobs now\n"
        "/keywords — View/update search keywords\n"
        "/subscribe — Auto-check on a schedule\n"
        "/unsubscribe — Stop auto-checks\n"
        "/status — Show your current settings"
    )


async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Searching for jobs...")

    cfg = context.bot_data
    db: JobsDB = cfg["db"]
    chat_id = _get_chat_id(update)
    keywords = db.get_keywords(chat_id) or cfg["default_keywords"]
    all_jobs = search_jobs(cfg["apify_token"], keywords, cfg["location"], cfg["experience_level"])

    new_jobs = []
    for job in all_jobs:
        if not db.is_seen(chat_id, job["id"]):
            new_jobs.append(job)
            db.mark_seen(chat_id, job["id"])

    for chunk in format_digest_chunks(new_jobs):
        await update.message.reply_text(chunk)


async def keywords_show(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = context.bot_data
    db: JobsDB = cfg["db"]
    chat_id = _get_chat_id(update)
    current = db.get_keywords(chat_id) or cfg["default_keywords"]
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

    db: JobsDB = context.bot_data["db"]
    chat_id = _get_chat_id(update)
    db.set_keywords(chat_id, new_keywords)
    await update.message.reply_text(
        "Updated keywords to:\n" + "\n".join(f"  - {kw}" for kw in new_keywords)
    )
    return ConversationHandler.END


async def subscribe_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "How often should I check for new jobs?\n\n"
        "Send a number in hours (e.g. 6, 12, 24) or /cancel:"
    )
    return WAITING_INTERVAL


async def subscribe_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        hours = int(update.message.text.strip())
        if hours < 1 or hours > 168:
            raise ValueError
    except ValueError:
        await update.message.reply_text("Send a number between 1 and 168, or /cancel.")
        return WAITING_INTERVAL

    db: JobsDB = context.bot_data["db"]
    chat_id = _get_chat_id(update)
    db.subscribe(chat_id, hours)

    _schedule_user_job(context, chat_id, hours)

    await update.message.reply_text(
        f"Subscribed! I'll check every {hours}h and send you new jobs."
    )
    return ConversationHandler.END


async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db: JobsDB = context.bot_data["db"]
    chat_id = _get_chat_id(update)

    if not db.is_subscribed(chat_id):
        await update.message.reply_text("You're not subscribed.")
        return

    db.unsubscribe(chat_id)
    _remove_user_job(context, chat_id)
    await update.message.reply_text("Unsubscribed. No more auto-checks.")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = context.bot_data
    db: JobsDB = cfg["db"]
    chat_id = _get_chat_id(update)

    keywords = db.get_keywords(chat_id) or cfg["default_keywords"]
    subscribed = db.is_subscribed(chat_id)

    text = "Your settings:\n\n"
    text += "Keywords:\n"
    for kw in keywords:
        text += f"  - {kw}\n"

    if subscribed:
        subs = db.get_subscribers()
        for s in subs:
            if s["chat_id"] == chat_id:
                text += f"\nAuto-check: every {s['interval_hours']}h"
                break
    else:
        text += "\nAuto-check: off (/subscribe to enable)"

    await update.message.reply_text(text)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END


async def _scheduled_check(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.data
    cfg = context.bot_data
    db: JobsDB = cfg["db"]

    keywords = db.get_keywords(chat_id) or cfg["default_keywords"]
    all_jobs = search_jobs(cfg["apify_token"], keywords, cfg["location"], cfg["experience_level"])

    new_jobs = []
    for job in all_jobs:
        if not db.is_seen(chat_id, job["id"]):
            new_jobs.append(job)
            db.mark_seen(chat_id, job["id"])

    if new_jobs:
        for chunk in format_digest_chunks(new_jobs):
            await context.bot.send_message(chat_id=chat_id, text=chunk)


def _schedule_user_job(context: ContextTypes.DEFAULT_TYPE, chat_id: str, interval_hours: int):
    _remove_user_job(context, chat_id)
    context.job_queue.run_repeating(
        _scheduled_check,
        interval=interval_hours * 3600,
        first=10,
        data=chat_id,
        name=f"check_{chat_id}",
    )


def _remove_user_job(context: ContextTypes.DEFAULT_TYPE, chat_id: str):
    jobs = context.job_queue.get_jobs_by_name(f"check_{chat_id}")
    for job in jobs:
        job.schedule_removal()


async def _restore_subscriptions(app):
    db: JobsDB = app.bot_data["db"]
    for sub in db.get_subscribers():
        app.job_queue.run_repeating(
            _scheduled_check,
            interval=sub["interval_hours"] * 3600,
            first=60,
            data=sub["chat_id"],
            name=f"check_{sub['chat_id']}",
        )


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
    app.add_handler(CommandHandler("unsubscribe", unsubscribe))
    app.add_handler(CommandHandler("status", status))

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

    subscribe_handler = ConversationHandler(
        entry_points=[CommandHandler("subscribe", subscribe_start)],
        states={
            WAITING_INTERVAL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, subscribe_set)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(subscribe_handler)

    app.post_init = _restore_subscriptions

    print("Bot is running. Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()
