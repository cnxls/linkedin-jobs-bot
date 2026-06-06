import os
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
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
from formatter import format_job_card

WAITING_KEYWORDS = 1
WAITING_INTERVAL = 2
WAITING_LOCATION = 3

EXPERIENCE_OPTIONS = [
    ("1", "Internship"),
    ("2", "Entry level"),
    ("3", "Associate"),
    ("4", "Mid-Senior"),
    ("5", "Director"),
]

JOB_TYPE_OPTIONS = [
    ("1", "On-site"),
    ("2", "Remote"),
    ("3", "Hybrid"),
]


def _format_exp(codes: str) -> str:
    if not codes:
        return "Any"
    lookup = dict(EXPERIENCE_OPTIONS)
    return ", ".join(lookup.get(c, c) for c in codes.split(","))


def _format_jt(codes: str) -> str:
    if not codes:
        return "Any"
    lookup = dict(JOB_TYPE_OPTIONS)
    return ", ".join(lookup.get(c, c) for c in codes.split(","))

WELCOME_IMAGE = Path(__file__).parent / "assets" / "welcome.png"
BOT_NAME = "LinkedIn Jobs Radar"


def _get_chat_id(update: Update) -> str:
    return str(update.effective_chat.id)


def _main_menu_keyboard(pending_count: int = 0) -> InlineKeyboardMarkup:
    check_label = "Search for jobs"
    if pending_count > 0:
        check_label = f"Search for jobs  ({pending_count} pending)"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(check_label, callback_data="cmd_check")],
        [
            InlineKeyboardButton("Keywords", callback_data="cmd_keywords"),
            InlineKeyboardButton("Settings", callback_data="cmd_settings"),
        ],
        [
            InlineKeyboardButton("Subscribe", callback_data="cmd_subscribe"),
            InlineKeyboardButton("Status", callback_data="cmd_status"),
        ],
        [
            InlineKeyboardButton("Unsubscribe", callback_data="cmd_unsubscribe"),
        ],
    ])


def _user_search_params(db: JobsDB, chat_id: str, cfg: dict) -> dict:
    prefs = db.get_all_preferences(chat_id)
    return {
        "location": prefs.get("location", cfg["location"]),
        "experience_level": prefs.get("experience_level", cfg["experience_level"]),
        "job_type": prefs.get("job_type", ""),
    }


async def _send(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, **kwargs):
    kwargs.setdefault("parse_mode", ParseMode.HTML)
    if update.callback_query:
        return await context.bot.send_message(
            chat_id=update.effective_chat.id, text=text, **kwargs
        )
    return await update.message.reply_text(text, **kwargs)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pending = context.user_data.get("pending_jobs", [])
    welcome = (
        f"<b>{BOT_NAME}</b>\n\n"
        "Your personal job search assistant.\n"
        "I scan LinkedIn for new internship and junior positions "
        "matching your keywords and deliver them straight here.\n\n"
        "<b>How it works:</b>\n"
        "1. Tap <b>Search for jobs</b> to find offers now\n"
        "2. Browse offers one by one\n"
        "3. Set up <b>Subscribe</b> for automatic checks\n\n"
        "Customize your <b>Keywords</b> to match your dream role."
    )

    if WELCOME_IMAGE.exists():
        with open(WELCOME_IMAGE, "rb") as photo:
            await update.message.reply_photo(
                photo=photo,
                caption=welcome,
                parse_mode=ParseMode.HTML,
                reply_markup=_main_menu_keyboard(len(pending)),
            )
    else:
        await update.message.reply_text(
            welcome,
            parse_mode=ParseMode.HTML,
            reply_markup=_main_menu_keyboard(len(pending)),
        )


async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        try:
            await query.edit_message_text("Scanning LinkedIn for new offers...")
        except Exception:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Scanning LinkedIn for new offers...",
            )

    cfg = context.bot_data
    db: JobsDB = cfg["db"]
    chat_id = _get_chat_id(update)
    keywords = db.get_keywords(chat_id) or cfg["default_keywords"]
    params = _user_search_params(db, chat_id, cfg)
    all_jobs = search_jobs(
        cfg["apify_token"], keywords,
        params["location"], params["experience_level"], params["job_type"],
    )

    new_jobs = []
    for job in all_jobs:
        if not db.is_seen(chat_id, job["id"]):
            new_jobs.append(job)
            db.mark_seen(chat_id, job["id"])

    if not new_jobs:
        await _send(
            update, context,
            "No new jobs found.\nTry adjusting your keywords or check back later.",
            reply_markup=_main_menu_keyboard(),
        )
        return

    context.user_data["pending_jobs"] = new_jobs
    context.user_data["pending_index"] = 0

    await _send(
        update, context,
        f"Found <b>{len(new_jobs)}</b> new offer(s)!",
    )
    await _send_next_job(update, context)


async def _send_next_job(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jobs = context.user_data.get("pending_jobs", [])
    idx = context.user_data.get("pending_index", 0)
    total = len(jobs)

    if idx >= total:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="That's all the offers!",
            parse_mode=ParseMode.HTML,
            reply_markup=_main_menu_keyboard(),
        )
        context.user_data["pending_jobs"] = []
        context.user_data["pending_index"] = 0
        return

    job = jobs[idx]
    remaining = total - idx - 1
    text = format_job_card(job, idx + 1, total)

    buttons = []
    if remaining > 0:
        buttons.append(InlineKeyboardButton(
            f"Next  ({remaining} left)", callback_data="next_job"
        ))
    buttons.append(InlineKeyboardButton("Done", callback_data="done_jobs"))

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([buttons]),
        disable_web_page_preview=True,
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
        text = f"Stopped. <b>{remaining}</b> offers skipped."
    else:
        text = "All offers shown!"

    await query.edit_message_reply_markup(reply_markup=None)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text,
        parse_mode=ParseMode.HTML,
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

    kw_list = "\n".join(f"  {kw}" for kw in current)
    text = (
        f"<b>Your Keywords</b>\n\n"
        f"<code>{kw_list}</code>\n\n"
        f"Send new keywords (comma-separated) or /cancel"
    )

    await _send(update, context, text)
    return WAITING_KEYWORDS


async def keywords_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text
    new_keywords = [kw.strip() for kw in raw.split(",") if kw.strip()]
    if not new_keywords:
        await update.message.reply_text(
            "No valid keywords. Try again or /cancel.",
            parse_mode=ParseMode.HTML,
        )
        return WAITING_KEYWORDS

    db: JobsDB = context.bot_data["db"]
    chat_id = _get_chat_id(update)
    db.set_keywords(chat_id, new_keywords)

    kw_list = "\n".join(f"  {kw}" for kw in new_keywords)
    await update.message.reply_text(
        f"<b>Keywords updated</b>\n\n<code>{kw_list}</code>",
        parse_mode=ParseMode.HTML,
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

    text = "<b>Auto-Check Schedule</b>\n\nHow often should I scan for new jobs?"
    await _send(update, context, text, reply_markup=buttons)
    return WAITING_INTERVAL


async def subscribe_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    if data == "sub_custom":
        await query.edit_message_text(
            "Send a number of hours (1-168):",
            parse_mode=ParseMode.HTML,
        )
        return WAITING_INTERVAL

    hours = int(data.split("_")[1])
    db: JobsDB = context.bot_data["db"]
    chat_id = _get_chat_id(update)
    db.subscribe(chat_id, hours)
    _schedule_user_job(context, chat_id, hours)

    await query.edit_message_text(
        f"Subscribed! I'll check every <b>{hours}h</b> and notify you about new offers.",
        parse_mode=ParseMode.HTML,
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
        await update.message.reply_text(
            "Send a number between 1 and 168, or /cancel.",
            parse_mode=ParseMode.HTML,
        )
        return WAITING_INTERVAL

    db: JobsDB = context.bot_data["db"]
    chat_id = _get_chat_id(update)
    db.subscribe(chat_id, hours)
    _schedule_user_job(context, chat_id, hours)

    await update.message.reply_text(
        f"Subscribed! I'll check every <b>{hours}h</b> and notify you about new offers.",
        parse_mode=ParseMode.HTML,
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
        text = "You're not subscribed to auto-checks."
    else:
        db.unsubscribe(chat_id)
        _remove_user_job(context, chat_id)
        text = "Unsubscribed. Auto-checks stopped."

    await _send(update, context, text, reply_markup=_main_menu_keyboard())


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

    kw_list = ", ".join(keywords)

    sub_status = "Off"
    if db.is_subscribed(chat_id):
        for s in db.get_subscribers():
            if s["chat_id"] == chat_id:
                sub_status = f"Every {s['interval_hours']}h"
                break

    params = _user_search_params(db, chat_id, cfg)
    loc = params["location"]
    exp = _format_exp(params["experience_level"])
    jt = _format_jt(params["job_type"])

    text = (
        f"<b>Your Dashboard</b>\n\n"
        f"<b>Keywords:</b> {kw_list}\n"
        f"<b>Location:</b> {loc}\n"
        f"<b>Experience:</b> {exp}\n"
        f"<b>Job type:</b> {jt}\n"
        f"<b>Auto-check:</b> {sub_status}\n"
    )

    if remaining > 0:
        text += f"<b>Pending offers:</b> {remaining}\n"

    await _send(update, context, text, reply_markup=_main_menu_keyboard(remaining))


async def settings_show(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()

    cfg = context.bot_data
    db: JobsDB = cfg["db"]
    chat_id = _get_chat_id(update)
    params = _user_search_params(db, chat_id, cfg)

    loc = params["location"]
    exp = _format_exp(params["experience_level"])
    jt = _format_jt(params["job_type"])

    text = (
        f"<b>Search Settings</b>\n\n"
        f"<b>Location:</b> {loc}\n"
        f"<b>Experience:</b> {exp}\n"
        f"<b>Job type:</b> {jt}\n\n"
        f"Tap a button to change:"
    )

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Location: {loc}", callback_data="set_location")],
        [InlineKeyboardButton(f"Experience: {exp}", callback_data="set_experience")],
        [InlineKeyboardButton(f"Job type: {jt}", callback_data="set_jobtype")],
        [InlineKeyboardButton("Back", callback_data="set_back")],
    ])

    await _send(update, context, text, reply_markup=buttons)


async def on_set_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Send the city or country name (e.g. <code>Kraków, Poland</code> or <code>Remote</code>).\n\nOr /cancel.",
        parse_mode=ParseMode.HTML,
    )
    return WAITING_LOCATION


async def on_location_typed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    location = update.message.text.strip()
    if not location:
        await update.message.reply_text("Send a valid location or /cancel.")
        return WAITING_LOCATION

    db: JobsDB = context.bot_data["db"]
    chat_id = _get_chat_id(update)
    db.set_preference(chat_id, "location", location)

    await update.message.reply_text(
        f"Location set to <b>{location}</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=_main_menu_keyboard(),
    )
    return ConversationHandler.END


def _toggle_code(current: str, code: str) -> str:
    codes = [c for c in current.split(",") if c] if current else []
    if code in codes:
        codes.remove(code)
    else:
        codes.append(code)
    return ",".join(codes)


def _build_toggle_buttons(options: list[tuple[str, str]], selected: str, prefix: str):
    codes = set(selected.split(",")) if selected else set()
    rows = []
    for code, label in options:
        check = "✅ " if code in codes else ""
        rows.append([InlineKeyboardButton(f"{check}{label}", callback_data=f"{prefix}_toggle_{code}")])
    rows.append([InlineKeyboardButton("Done", callback_data=f"{prefix}_done")])
    return InlineKeyboardMarkup(rows)


async def on_set_experience(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    db: JobsDB = context.bot_data["db"]
    chat_id = _get_chat_id(update)
    current = db.get_preference(chat_id, "experience_level") or context.bot_data["experience_level"]

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="<b>Select experience levels</b>\n(tap to toggle, then Done):",
        parse_mode=ParseMode.HTML,
        reply_markup=_build_toggle_buttons(EXPERIENCE_OPTIONS, current, "exp"),
    )


async def on_exp_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    code = query.data.removeprefix("exp_toggle_")
    db: JobsDB = context.bot_data["db"]
    chat_id = _get_chat_id(update)
    current = db.get_preference(chat_id, "experience_level") or context.bot_data["experience_level"]

    new_val = _toggle_code(current, code)
    db.set_preference(chat_id, "experience_level", new_val)

    await query.edit_message_reply_markup(
        reply_markup=_build_toggle_buttons(EXPERIENCE_OPTIONS, new_val, "exp"),
    )


async def on_exp_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    db: JobsDB = context.bot_data["db"]
    chat_id = _get_chat_id(update)
    current = db.get_preference(chat_id, "experience_level") or ""
    label = _format_exp(current)

    await query.edit_message_text(
        f"Experience set to <b>{label}</b>",
        parse_mode=ParseMode.HTML,
    )
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Menu:",
        reply_markup=_main_menu_keyboard(),
    )


async def on_set_jobtype(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    db: JobsDB = context.bot_data["db"]
    chat_id = _get_chat_id(update)
    current = db.get_preference(chat_id, "job_type") or ""

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="<b>Select job types</b>\n(tap to toggle, then Done):",
        parse_mode=ParseMode.HTML,
        reply_markup=_build_toggle_buttons(JOB_TYPE_OPTIONS, current, "jt"),
    )


async def on_jt_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    code = query.data.removeprefix("jt_toggle_")
    db: JobsDB = context.bot_data["db"]
    chat_id = _get_chat_id(update)
    current = db.get_preference(chat_id, "job_type") or ""

    new_val = _toggle_code(current, code)
    db.set_preference(chat_id, "job_type", new_val)

    await query.edit_message_reply_markup(
        reply_markup=_build_toggle_buttons(JOB_TYPE_OPTIONS, new_val, "jt"),
    )


async def on_jt_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    db: JobsDB = context.bot_data["db"]
    chat_id = _get_chat_id(update)
    current = db.get_preference(chat_id, "job_type") or ""
    label = _format_jt(current)

    await query.edit_message_text(
        f"Job type set to <b>{label}</b>",
        parse_mode=ParseMode.HTML,
    )
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Menu:",
        reply_markup=_main_menu_keyboard(),
    )


async def on_set_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Menu:",
        reply_markup=_main_menu_keyboard(),
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Cancelled.",
        parse_mode=ParseMode.HTML,
        reply_markup=_main_menu_keyboard(),
    )
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
    elif data == "cmd_settings":
        await settings_show(update, context)


async def _scheduled_check(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.data
    cfg = context.bot_data
    db: JobsDB = cfg["db"]

    keywords = db.get_keywords(chat_id) or cfg["default_keywords"]
    params = _user_search_params(db, chat_id, cfg)
    all_jobs = search_jobs(
        cfg["apify_token"], keywords,
        params["location"], params["experience_level"], params["job_type"],
    )

    new_jobs = []
    for job in all_jobs:
        if not db.is_seen(chat_id, job["id"]):
            new_jobs.append(job)
            db.mark_seen(chat_id, job["id"])

    if not new_jobs:
        return

    await context.bot.send_message(
        chat_id=chat_id,
        text=f"Found <b>{len(new_jobs)}</b> new offer(s)!",
        parse_mode=ParseMode.HTML,
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

    settings_location_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(on_set_location, pattern="^set_location$"),
        ],
        states={
            WAITING_LOCATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, on_location_typed),
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(settings_location_handler)

    app.add_handler(CallbackQueryHandler(on_set_experience, pattern="^set_experience$"))
    app.add_handler(CallbackQueryHandler(on_exp_toggle, pattern="^exp_toggle_"))
    app.add_handler(CallbackQueryHandler(on_exp_done, pattern="^exp_done$"))
    app.add_handler(CallbackQueryHandler(on_set_jobtype, pattern="^set_jobtype$"))
    app.add_handler(CallbackQueryHandler(on_jt_toggle, pattern="^jt_toggle_"))
    app.add_handler(CallbackQueryHandler(on_jt_done, pattern="^jt_done$"))
    app.add_handler(CallbackQueryHandler(on_set_back, pattern="^set_back$"))

    app.add_handler(CallbackQueryHandler(on_menu_button, pattern="^cmd_"))

    app.post_init = _restore_subscriptions

    print("Bot is running. Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()
