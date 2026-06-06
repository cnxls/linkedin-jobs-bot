import json

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    ConversationHandler,
)

from db import JobsDB
from scraper import search_jobs
from formatter import format_single_job

WAITING_KEYWORDS = 1
WAITING_INTERVAL = 2


def _get_chat_id(update: Update) -> str:
    return str(update.effective_chat.id)


def _main_menu_keyboard(pending_count: int = 0) -> InlineKeyboardMarkup:
    check_label = "Search for jobs"
    if pending_count > 0:
        check_label = f"Search for jobs ({pending_count} pending)"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(check_label, callback_data="cmd_check")],
        [InlineKeyboardButton("My keywords", callback_data="cmd_keywords")],
        [
            InlineKeyboardButton("Subscribe", callback_data="cmd_subscribe"),
            InlineKeyboardButton("Unsubscribe", callback_data="cmd_unsubscribe"),
        ],
        [InlineKeyboardButton("Status", callback_data="cmd_status")],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = _get_chat_id(update)
    pending = context.user_data.get("pending_jobs", [])
    await update.message.reply_text(
        "LinkedIn Jobs Bot",
        reply_markup=_main_menu_keyboard(len(pending)),
    )


async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text("Searching for jobs...")
        send = lambda text, **kw: context.bot.send_message(
            chat_id=update.effective_chat.id, text=text, **kw
        )
    else:
        await update.message.reply_text("Searching for jobs...")
        send = update.message.reply_text

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

    if not new_jobs:
        await send("No new jobs found.", reply_markup=_main_menu_keyboard())
        return

    context.user_data["pending_jobs"] = new_jobs
    context.user_data["pending_index"] = 0

    await _send_next_job(update, context)


async def _send_next_job(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jobs = context.user_data.get("pending_jobs", [])
    idx = context.user_data.get("pending_index", 0)

    if idx >= len(jobs):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="No more offers.",
            reply_markup=_main_menu_keyboard(),
        )
        context.user_data["pending_jobs"] = []
        context.user_data["pending_index"] = 0
        return

    job = jobs[idx]
    remaining = len(jobs) - idx - 1
    text = format_single_job(job, idx + 1)

    buttons = []
    if remaining > 0:
        buttons.append(InlineKeyboardButton(
            f"Next offer ({remaining} left)", callback_data="next_job"
        ))
    buttons.append(InlineKeyboardButton("Done", callback_data="done_jobs"))

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=InlineKeyboardMarkup([buttons]),
    )
    context.user_data["pending_index"] = idx + 1


async def on_next_job(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await _send_next_job(update, context)


async def on_done_jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    remaining = len(context.user_data.get("pending_jobs", [])) - context.user_data.get("pending_index", 0)
    context.user_data["pending_jobs"] = []
    context.user_data["pending_index"] = 0
    if remaining > 0:
        text = f"Stopped. {remaining} offers skipped."
    else:
        text = "All offers shown."
    await query.edit_message_reply_markup(reply_markup=None)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        reply_markup=_main_menu_keyboard(),
    )


async def keywords_show(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()

    cfg = context.bot_data
    db: JobsDB = cfg["db"]
    chat_id = _get_chat_id(update)
    current = db.get_keywords(chat_id) or cfg["default_keywords"]
    text = "Current keywords:\n"
    for kw in current:
        text += f"  - {kw}\n"
    text += "\nSend new keywords (comma-separated) or /cancel:"

    if query:
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=text
        )
    else:
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
        "Updated keywords to:\n" + "\n".join(f"  - {kw}" for kw in new_keywords),
        reply_markup=_main_menu_keyboard(),
    )
    return ConversationHandler.END


async def subscribe_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()

    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Every 6h", callback_data="sub_6"),
            InlineKeyboardButton("Every 12h", callback_data="sub_12"),
        ],
        [
            InlineKeyboardButton("Every 24h", callback_data="sub_24"),
            InlineKeyboardButton("Custom", callback_data="sub_custom"),
        ],
    ])

    text = "How often should I check for new jobs?"
    if query:
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=text, reply_markup=buttons
        )
    else:
        await update.message.reply_text(text, reply_markup=buttons)
    return WAITING_INTERVAL


async def subscribe_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    if data == "sub_custom":
        await query.edit_message_text("Send a number of hours (1-168):")
        return WAITING_INTERVAL

    hours = int(data.split("_")[1])
    db: JobsDB = context.bot_data["db"]
    chat_id = _get_chat_id(update)
    db.subscribe(chat_id, hours)
    _schedule_user_job(context, chat_id, hours)

    await query.edit_message_text(
        f"Subscribed! I'll check every {hours}h and send you new jobs."
    )
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Menu:",
        reply_markup=_main_menu_keyboard(),
    )
    return ConversationHandler.END


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
        f"Subscribed! I'll check every {hours}h and send you new jobs.",
        reply_markup=_main_menu_keyboard(),
    )
    return ConversationHandler.END


async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()

    db: JobsDB = context.bot_data["db"]
    chat_id = _get_chat_id(update)

    if not db.is_subscribed(chat_id):
        text = "You're not subscribed."
    else:
        db.unsubscribe(chat_id)
        _remove_user_job(context, chat_id)
        text = "Unsubscribed. No more auto-checks."

    if query:
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=text,
            reply_markup=_main_menu_keyboard(),
        )
    else:
        await update.message.reply_text(text, reply_markup=_main_menu_keyboard())


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()

    cfg = context.bot_data
    db: JobsDB = cfg["db"]
    chat_id = _get_chat_id(update)

    keywords = db.get_keywords(chat_id) or cfg["default_keywords"]
    pending = context.user_data.get("pending_jobs", [])
    pending_idx = context.user_data.get("pending_index", 0)
    remaining = max(0, len(pending) - pending_idx)

    text = "Your settings:\n\n"
    text += "Keywords:\n"
    for kw in keywords:
        text += f"  - {kw}\n"

    if db.is_subscribed(chat_id):
        for s in db.get_subscribers():
            if s["chat_id"] == chat_id:
                text += f"\nAuto-check: every {s['interval_hours']}h"
                break
    else:
        text += "\nAuto-check: off"

    if remaining > 0:
        text += f"\nPending offers: {remaining}"

    if query:
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=text,
            reply_markup=_main_menu_keyboard(remaining),
        )
    else:
        await update.message.reply_text(text, reply_markup=_main_menu_keyboard(remaining))


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled.", reply_markup=_main_menu_keyboard())
    return ConversationHandler.END


async def on_menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data == "cmd_check":
        await check(update, context)
    elif data == "cmd_keywords":
        await keywords_show(update, context)
    elif data == "cmd_subscribe":
        await subscribe_start(update, context)
    elif data == "cmd_unsubscribe":
        await unsubscribe(update, context)
    elif data == "cmd_status":
        await status(update, context)


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

    if not new_jobs:
        return

    await context.bot.send_message(
        chat_id=chat_id,
        text=f"Found {len(new_jobs)} new job(s)!",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Show offers", callback_data="show_scheduled")],
        ]),
    )

    user_data = context.application.user_data.setdefault(int(chat_id), {})
    user_data["pending_jobs"] = new_jobs
    user_data["pending_index"] = 0


async def on_show_scheduled(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await _send_next_job(update, context)


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

    app.add_handler(CallbackQueryHandler(on_next_job, pattern="^next_job$"))
    app.add_handler(CallbackQueryHandler(on_done_jobs, pattern="^done_jobs$"))
    app.add_handler(CallbackQueryHandler(on_show_scheduled, pattern="^show_scheduled$"))

    keywords_handler = ConversationHandler(
        entry_points=[
            CommandHandler("keywords", keywords_show),
            CallbackQueryHandler(keywords_show, pattern="^cmd_keywords$"),
        ],
        states={
            WAITING_KEYWORDS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, keywords_update)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(keywords_handler)

    subscribe_handler = ConversationHandler(
        entry_points=[
            CommandHandler("subscribe", subscribe_start),
            CallbackQueryHandler(subscribe_start, pattern="^cmd_subscribe$"),
        ],
        states={
            WAITING_INTERVAL: [
                CallbackQueryHandler(subscribe_button, pattern="^sub_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, subscribe_set),
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(subscribe_handler)

    app.add_handler(CallbackQueryHandler(on_menu_button, pattern="^cmd_"))

    app.post_init = _restore_subscriptions

    print("Bot is running. Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()
