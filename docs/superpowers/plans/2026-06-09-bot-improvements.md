# LinkedIn Jobs Bot Improvements — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 7 features to the LinkedIn job scraper Telegram bot: back button, unsave individual jobs, search presets, keyword exclusions, logging system, online/offline status, and user-friendly UX improvements.

**Architecture:** Each feature is a self-contained task that modifies `db.py` (data layer), `bot.py` (handlers/UI), and related modules. A new `logger.py` module centralizes logging configuration. All features are independent except: Task 3 (unsave) depends on Task 2's `remove_saved_job` DB method, and Task 6 (online/offline) uses logging from Task 1.

**Tech Stack:** Python 3.13, python-telegram-bot v22, SQLite, Python stdlib `logging` with `TimedRotatingFileHandler`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `logger.py` | Create | Centralized logging config with daily rotating file handler |
| `db.py` | Modify | Add `presets` table, `remove_saved_job()`, exclusions storage |
| `bot.py` | Modify | All UI changes: back button, saved browse, presets, exclusions, status, help, tips |
| `scraper.py` | Modify | Add logging to Apify calls |
| `digest.py` | Modify | Add logging |
| `config.py` | Modify | Add `LOG_DIR` path |
| `.gitignore` | Modify | Add `logs/` |
| `tests/test_db.py` | Modify | Tests for presets, remove_saved_job, exclusions |
| `tests/test_logger.py` | Create | Tests for logging setup |

---

### Task 1: Logging System

**Files:**
- Create: `logger.py`
- Create: `tests/test_logger.py`
- Modify: `config.py:12` (add LOG_DIR)
- Modify: `.gitignore:5` (add logs/)
- Modify: `scraper.py:1-6` (add logging)
- Modify: `bot.py:1-2,878-964` (add logging to main, check, scheduled_check)
- Modify: `digest.py:1-2,12-40` (add logging)

- [ ] **Step 1: Add `logs/` to `.gitignore` and `LOG_DIR` to config**

In `.gitignore`, add at the end:
```
logs/
```

In `config.py`, add after line 12 (`DB_PATH = ...`):
```python
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
```

- [ ] **Step 2: Write the failing test for logger setup**

Create `tests/test_logger.py`:
```python
import os
import logging
from unittest.mock import patch


def test_setup_logging_creates_log_dir(tmp_path):
    log_dir = str(tmp_path / "logs")
    from logger import setup_logging
    setup_logging(log_dir)
    assert os.path.isdir(log_dir)


def test_setup_logging_returns_logger(tmp_path):
    log_dir = str(tmp_path / "logs")
    from logger import setup_logging
    log = setup_logging(log_dir)
    assert isinstance(log, logging.Logger)
    assert log.name == "linkedin_bot"


def test_setup_logging_writes_to_file(tmp_path):
    log_dir = str(tmp_path / "logs")
    from logger import setup_logging
    log = setup_logging(log_dir)
    log.info("test message")
    log_files = os.listdir(log_dir)
    assert len(log_files) >= 1
    content = open(os.path.join(log_dir, log_files[0])).read()
    assert "test message" in content


def test_setup_logging_idempotent(tmp_path):
    log_dir = str(tmp_path / "logs")
    from logger import setup_logging
    log1 = setup_logging(log_dir)
    log2 = setup_logging(log_dir)
    assert log1 is log2
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd C:\crap\linkedin-jobs-bot && python -m pytest tests/test_logger.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'logger'`

- [ ] **Step 4: Implement `logger.py`**

Create `logger.py`:
```python
import os
import logging
from logging.handlers import TimedRotatingFileHandler

_logger = None


def setup_logging(log_dir: str) -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger

    os.makedirs(log_dir, exist_ok=True)

    logger = logging.getLogger("linkedin_bot")
    logger.setLevel(logging.INFO)

    file_handler = TimedRotatingFileHandler(
        os.path.join(log_dir, "bot.log"),
        when="midnight",
        backupCount=30,
        encoding="utf-8",
    )
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
    )
    logger.addHandler(console_handler)

    _logger = logger
    return logger
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd C:\crap\linkedin-jobs-bot && python -m pytest tests/test_logger.py -v`
Expected: 4 passed

- [ ] **Step 6: Add logging to `scraper.py`**

Add at top of `scraper.py` (after line 3):
```python
import logging

log = logging.getLogger("linkedin_bot")
```

Wrap the Apify call in `search_jobs` (around lines 59-72) — replace the existing body of `search_jobs` from `client = ApifyClient(...)` onward with:
```python
    client = ApifyClient(apify_token)

    urls = [
        build_linkedin_search_url(kw, location, experience_level, job_type)
        for kw in keywords
    ]

    run_input = {
        "urls": urls,
        "count": 25,
        "scrapeCompany": False,
    }

    log.info("Starting Apify scrape: %d keywords, location=%s", len(keywords), location)

    try:
        run = client.actor(ACTOR_ID).call(run_input=run_input)
    except Exception:
        log.exception("Apify actor call failed")
        return []

    all_jobs = []
    dataset_id = getattr(run, "default_dataset_id", None) or (run.get("defaultDatasetId") if isinstance(run, dict) else None)
    if dataset_id:
        for item in client.dataset(dataset_id).iterate_items():
            all_jobs.append(parse_job_item(item))

    log.info("Scrape complete: %d jobs found", len(all_jobs))

    if len(all_jobs) == 0:
        log.warning("Scraper returned 0 results — possible LinkedIn block or bad query")

    return all_jobs
```

- [ ] **Step 7: Add logging to `bot.py`**

Add at top of `bot.py` (after line 2):
```python
import time
```

Add after the existing imports (after line 14):
```python
from logger import setup_logging
```

In the `main()` function (around line 878), add after config imports and before `app = ApplicationBuilder()...`:
```python
    from config import LOG_DIR
    log = setup_logging(LOG_DIR)
    log.info("Bot starting up")
```

Replace the `print("Bot is running...")` line (line 963) with:
```python
    log.info("Bot polling started")
```

In `check()` (around line 129), add logging after `all_jobs = search_jobs(...)` (after line 152):
```python
    log.info("Manual check by %s: %d new jobs out of %d total", chat_id, len(new_jobs), len(all_jobs))
```
(Add `log = logging.getLogger("linkedin_bot")` at the top of bot.py after imports, and `import logging` with the other imports.)

In `_scheduled_check()` (around line 803), add logging after the new_jobs loop (after line 819):
```python
    log = logging.getLogger("linkedin_bot")
    log.info("Scheduled check for %s: %d new jobs", chat_id, len(new_jobs))
```

- [ ] **Step 8: Add logging to `digest.py`**

Add at top of `digest.py` (after line 2):
```python
import logging

log = logging.getLogger("linkedin_bot")
```

Replace the `print(...)` at line 40 with:
```python
    log.info("Digest sent to %s: %d new jobs", chat_id, len(new_jobs))
```

- [ ] **Step 9: Run all tests**

Run: `cd C:\crap\linkedin-jobs-bot && python -m pytest -v`
Expected: All tests pass (existing + 4 new logger tests)

- [ ] **Step 10: Commit**

```bash
git add logger.py tests/test_logger.py config.py .gitignore scraper.py bot.py digest.py
git commit -m "feat: add logging system with daily rotating log files"
```

---

### Task 2: Back Button in Job Browse

**Files:**
- Modify: `bot.py:203-260` (add Back button to browse keyboard, add `on_prev_job` handler)
- Modify: `bot.py:896-964` (register new handler)

- [ ] **Step 1: Add `on_prev_job` handler to `bot.py`**

Add after the `on_next_job` function (after line 266):
```python
async def on_prev_job(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    idx = context.user_data.get("pending_index", 0)
    context.user_data["pending_index"] = max(0, idx - 2)
    await _send_next_job(update, context)
```

Explanation of `idx - 2`: `pending_index` is always 1 ahead of the currently displayed job (it's incremented after display). So `idx - 1` is the current job, `idx - 2` is the previous job. `_send_next_job` will read the new index, display that job, and increment again.

- [ ] **Step 2: Add Back button to the browse keyboard in `_send_next_job`**

In `_send_next_job` (around line 233), replace the button-building block:
```python
    buttons = [InlineKeyboardButton("Save", callback_data="save_job")]
    if remaining > 0:
        buttons.append(InlineKeyboardButton(
            f"Next  ({remaining} left)", callback_data="next_job"
        ))
    buttons.append(InlineKeyboardButton("Done", callback_data="done_jobs"))
```

With:
```python
    buttons = []
    if idx > 0:
        buttons.append(InlineKeyboardButton("Back", callback_data="prev_job"))
    buttons.append(InlineKeyboardButton("Save", callback_data="save_job"))
    if remaining > 0:
        buttons.append(InlineKeyboardButton(
            f"Next ({remaining} left)", callback_data="next_job"
        ))
    buttons.append(InlineKeyboardButton("Done", callback_data="done_jobs"))
```

- [ ] **Step 3: Register the handler in `main()`**

In `main()`, add after the `on_next_job` handler registration (after line 903):
```python
    app.add_handler(CallbackQueryHandler(on_prev_job, pattern="^prev_job$"))
```

- [ ] **Step 4: Run all tests**

Run: `cd C:\crap\linkedin-jobs-bot && python -m pytest -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add bot.py
git commit -m "feat: add back button to job browse flow"
```

---

### Task 3: Browse & Unsave Individual Saved Jobs

**Files:**
- Modify: `db.py:175-179` (add `remove_saved_job` method)
- Modify: `bot.py:718-780` (rewrite saved_jobs_show to one-by-one browse)
- Modify: `bot.py:896-964` (register new handlers)
- Modify: `tests/test_db.py` (add tests for remove_saved_job)

- [ ] **Step 1: Write failing test for `remove_saved_job`**

Add to `tests/test_db.py`:
```python
def test_save_and_remove_job(db):
    job = {
        "id": "job1",
        "title": "ML Intern",
        "company": "Google",
        "location": "Kraków",
        "salary": None,
        "posted_at": "2026-06-05",
        "url": "https://linkedin.com/jobs/view/1",
        "description": "Great role.",
    }
    db.save_job("user1", job)
    assert len(db.get_saved_jobs("user1")) == 1
    db.remove_saved_job("user1", "job1")
    assert len(db.get_saved_jobs("user1")) == 0


def test_remove_saved_job_isolated(db):
    job = {
        "id": "job1",
        "title": "ML Intern",
        "company": "Google",
        "location": "Kraków",
        "salary": None,
        "posted_at": "2026-06-05",
        "url": "https://linkedin.com/jobs/view/1",
        "description": "Great role.",
    }
    db.save_job("user1", job)
    db.save_job("user2", job)
    db.remove_saved_job("user1", "job1")
    assert len(db.get_saved_jobs("user1")) == 0
    assert len(db.get_saved_jobs("user2")) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:\crap\linkedin-jobs-bot && python -m pytest tests/test_db.py::test_save_and_remove_job -v`
Expected: FAIL — `AttributeError: 'JobsDB' object has no attribute 'remove_saved_job'`

- [ ] **Step 3: Implement `remove_saved_job` in `db.py`**

Add after `clear_saved_jobs` (after line 179):
```python
    def remove_saved_job(self, chat_id: str, job_id: str):
        self._conn.execute(
            "DELETE FROM saved_jobs WHERE chat_id = ? AND job_id = ?",
            (chat_id, job_id),
        )
        self._conn.commit()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:\crap\linkedin-jobs-bot && python -m pytest tests/test_db.py -v`
Expected: All pass (22 tests)

- [ ] **Step 5: Rewrite `saved_jobs_show` and add browse handlers in `bot.py`**

Replace the entire `saved_jobs_show` function (lines 718-764) and `on_clear_saved` function (lines 767-780) with:

```python
async def saved_jobs_show(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()

    cfg = context.bot_data
    db: JobsDB = cfg["db"]
    chat_id = _get_chat_id(update)
    jobs = db.get_saved_jobs(chat_id)

    if not jobs:
        await _send(
            update, context,
            "No saved jobs yet.",
            reply_markup=_main_menu_keyboard(),
        )
        return

    context.user_data["saved_list"] = jobs
    context.user_data["saved_index"] = 0
    context.user_data["saved_browse_msg_id"] = None
    await _send_next_saved(update, context)


async def _send_next_saved(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jobs = context.user_data.get("saved_list", [])
    idx = context.user_data.get("saved_index", 0)
    total = len(jobs)
    chat_id = update.effective_chat.id
    browse_msg_id = context.user_data.get("saved_browse_msg_id")

    if idx >= total:
        remaining = len(context.bot_data["db"].get_saved_jobs(str(chat_id)))
        text = f"End of saved jobs. <b>{remaining}</b> saved total."
        keyboard = _main_menu_keyboard()
        context.user_data["saved_list"] = []
        context.user_data["saved_index"] = 0
        context.user_data["saved_browse_msg_id"] = None

        if browse_msg_id:
            await context.bot.edit_message_text(
                chat_id=chat_id, message_id=browse_msg_id,
                text=text, parse_mode=ParseMode.HTML, reply_markup=keyboard,
            )
        else:
            await context.bot.send_message(
                chat_id=chat_id, text=text,
                parse_mode=ParseMode.HTML, reply_markup=keyboard,
            )
        return

    job = jobs[idx]
    text = format_job_card(job, idx + 1, total)

    buttons = []
    if idx > 0:
        buttons.append(InlineKeyboardButton("Back", callback_data="saved_prev"))
    buttons.append(InlineKeyboardButton("Remove", callback_data="saved_remove"))
    if idx + 1 < total:
        buttons.append(InlineKeyboardButton(
            f"Next ({total - idx - 1} left)", callback_data="saved_next"
        ))
    buttons.append(InlineKeyboardButton("Done", callback_data="saved_done"))

    keyboard = InlineKeyboardMarkup([
        buttons,
        [InlineKeyboardButton("Open on LinkedIn", url=job.get("url", ""))],
    ])
    context.user_data["saved_index"] = idx + 1

    if browse_msg_id:
        await context.bot.edit_message_text(
            chat_id=chat_id, message_id=browse_msg_id,
            text=text, parse_mode=ParseMode.HTML,
            reply_markup=keyboard, disable_web_page_preview=True,
        )
    else:
        msg = await context.bot.send_message(
            chat_id=chat_id, text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard, disable_web_page_preview=True,
        )
        context.user_data["saved_browse_msg_id"] = msg.message_id


async def on_saved_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await _send_next_saved(update, context)


async def on_saved_prev(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    idx = context.user_data.get("saved_index", 0)
    context.user_data["saved_index"] = max(0, idx - 2)
    await _send_next_saved(update, context)


async def on_saved_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    db: JobsDB = context.bot_data["db"]
    chat_id = _get_chat_id(update)

    jobs = context.user_data.get("saved_list", [])
    idx = context.user_data.get("saved_index", 0)
    current_idx = idx - 1

    if current_idx < 0 or current_idx >= len(jobs):
        return

    job = jobs[current_idx]
    db.remove_saved_job(chat_id, job["id"])
    jobs.pop(current_idx)
    context.user_data["saved_list"] = jobs
    context.user_data["saved_index"] = current_idx

    await _send_next_saved(update, context)


async def on_saved_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    remaining = len(context.bot_data["db"].get_saved_jobs(_get_chat_id(update)))
    text = f"<b>{remaining}</b> saved jobs remaining."

    browse_msg_id = context.user_data.get("saved_browse_msg_id")
    context.user_data["saved_list"] = []
    context.user_data["saved_index"] = 0
    context.user_data["saved_browse_msg_id"] = None

    if browse_msg_id:
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id, message_id=browse_msg_id,
            text=text, parse_mode=ParseMode.HTML,
            reply_markup=_main_menu_keyboard(),
        )
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text, parse_mode=ParseMode.HTML,
            reply_markup=_main_menu_keyboard(),
        )


async def on_clear_saved(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    cfg = context.bot_data
    db: JobsDB = cfg["db"]
    chat_id = _get_chat_id(update)
    db.clear_saved_jobs(chat_id)

    await query.edit_message_text(
        "Saved jobs cleared.",
        parse_mode=ParseMode.HTML,
        reply_markup=_main_menu_keyboard(),
    )
```

- [ ] **Step 6: Register saved browse handlers in `main()`**

In `main()`, add after the existing `on_clear_saved` handler:
```python
    app.add_handler(CallbackQueryHandler(on_saved_next, pattern="^saved_next$"))
    app.add_handler(CallbackQueryHandler(on_saved_prev, pattern="^saved_prev$"))
    app.add_handler(CallbackQueryHandler(on_saved_remove, pattern="^saved_remove$"))
    app.add_handler(CallbackQueryHandler(on_saved_done, pattern="^saved_done$"))
```

- [ ] **Step 7: Run all tests**

Run: `cd C:\crap\linkedin-jobs-bot && python -m pytest -v`
Expected: All pass

- [ ] **Step 8: Commit**

```bash
git add db.py bot.py tests/test_db.py
git commit -m "feat: browse saved jobs one-by-one with remove button"
```

---

### Task 4: Keyword Exclusions (Global Blacklist)

**Files:**
- Modify: `bot.py` (add exclusions settings UI, filter logic)
- Modify: `tests/test_db.py` (test exclusions via preferences)

- [ ] **Step 1: Write tests for exclusion filtering logic**

Add to `tests/test_db.py`:
```python
def test_exclusion_preference(db):
    db.set_preference("user1", "exclusions", "Senior,Lead,Manager")
    assert db.get_preference("user1", "exclusions") == "Senior,Lead,Manager"
```

Create a new file `tests/test_exclusions.py`:
```python
from bot import _filter_excluded


def test_filter_excluded_removes_matching():
    jobs = [
        {"id": "1", "title": "Senior ML Engineer"},
        {"id": "2", "title": "ML Intern"},
        {"id": "3", "title": "Lead Developer"},
        {"id": "4", "title": "Junior Python Dev"},
    ]
    filtered = _filter_excluded(jobs, "Senior,Lead")
    assert len(filtered) == 2
    assert filtered[0]["id"] == "2"
    assert filtered[1]["id"] == "4"


def test_filter_excluded_case_insensitive():
    jobs = [
        {"id": "1", "title": "senior ml engineer"},
        {"id": "2", "title": "ML Intern"},
    ]
    filtered = _filter_excluded(jobs, "Senior")
    assert len(filtered) == 1
    assert filtered[0]["id"] == "2"


def test_filter_excluded_empty_exclusions():
    jobs = [{"id": "1", "title": "ML Intern"}]
    assert _filter_excluded(jobs, "") == jobs
    assert _filter_excluded(jobs, None) == jobs
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:\crap\linkedin-jobs-bot && python -m pytest tests/test_exclusions.py -v`
Expected: FAIL — `ImportError: cannot import name '_filter_excluded' from 'bot'`

- [ ] **Step 3: Add `_filter_excluded` function to `bot.py`**

Add after the `_format_jt` function (after line 50):
```python
def _filter_excluded(jobs: list[dict], exclusions: str | None) -> list[dict]:
    if not exclusions:
        return jobs
    terms = [t.strip().lower() for t in exclusions.split(",") if t.strip()]
    if not terms:
        return jobs
    return [j for j in jobs if not any(t in j.get("title", "").lower() for t in terms)]
```

- [ ] **Step 4: Run exclusion tests to verify they pass**

Run: `cd C:\crap\linkedin-jobs-bot && python -m pytest tests/test_exclusions.py -v`
Expected: 3 passed

- [ ] **Step 5: Integrate exclusion filtering into `check()` and `_scheduled_check()`**

In `check()`, after getting `all_jobs` from `search_jobs(...)` (after line 152), add:
```python
    exclusions = db.get_preference(chat_id, "exclusions")
    all_jobs = _filter_excluded(all_jobs, exclusions)
```

In `_scheduled_check()`, after getting `all_jobs` from `search_jobs(...)` (after line 813), add:
```python
    exclusions = db.get_preference(chat_id, "exclusions")
    all_jobs = _filter_excluded(all_jobs, exclusions)
```

- [ ] **Step 6: Add exclusions UI to settings**

Add a new conversation state constant at top of `bot.py` (after line 23):
```python
WAITING_EXCLUSIONS = 4
```

Add after `on_set_back` (after line 706):
```python
async def on_set_exclusions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    db: JobsDB = context.bot_data["db"]
    chat_id = _get_chat_id(update)
    current = db.get_preference(chat_id, "exclusions") or ""

    display = current if current else "None"
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=(
            f"<b>Keyword Exclusions</b>\n\n"
            f"Current: <code>{display}</code>\n\n"
            f"Jobs with these words in the title will be hidden.\n"
            f"Send comma-separated words (e.g. <code>Senior, Lead, Manager</code>)\n"
            f"or send <code>clear</code> to remove all.\n\nOr /cancel."
        ),
        parse_mode=ParseMode.HTML,
    )
    return WAITING_EXCLUSIONS


async def on_exclusions_typed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text.strip()

    db: JobsDB = context.bot_data["db"]
    chat_id = _get_chat_id(update)

    if raw.lower() == "clear":
        db.set_preference(chat_id, "exclusions", "")
        await update.message.reply_text(
            "Exclusions cleared.",
            parse_mode=ParseMode.HTML,
            reply_markup=_main_menu_keyboard(),
        )
        return ConversationHandler.END

    terms = [t.strip() for t in raw.split(",") if t.strip()]
    if not terms:
        await update.message.reply_text("Send valid keywords or /cancel.")
        return WAITING_EXCLUSIONS

    value = ",".join(terms)
    db.set_preference(chat_id, "exclusions", value)

    await update.message.reply_text(
        f"Exclusions set: <code>{value}</code>\nJobs with these words in the title will be filtered out.",
        parse_mode=ParseMode.HTML,
        reply_markup=_main_menu_keyboard(),
    )
    return ConversationHandler.END
```

- [ ] **Step 7: Add exclusions button to `settings_show`**

In `settings_show()` (around line 527), after the job type line and before the "Tap a button" line, add:
```python
    excl = db.get_preference(chat_id, "exclusions") or "None"
```

Update the text to include:
```python
        f"<b>Exclusions:</b> {excl}\n\n"
```

Add a button to the keyboard (before the Back button):
```python
        [InlineKeyboardButton(f"Exclusions: {excl}", callback_data="set_exclusions")],
```

- [ ] **Step 8: Register the exclusions conversation handler and callback in `main()`**

Add in `main()`, after the `settings_location_handler`:
```python
    exclusions_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(on_set_exclusions, pattern="^set_exclusions$"),
        ],
        states={
            WAITING_EXCLUSIONS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, on_exclusions_typed),
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(exclusions_handler)
```

- [ ] **Step 9: Run all tests**

Run: `cd C:\crap\linkedin-jobs-bot && python -m pytest -v`
Expected: All pass

- [ ] **Step 10: Commit**

```bash
git add bot.py tests/test_exclusions.py tests/test_db.py
git commit -m "feat: add global keyword exclusions to filter jobs by title"
```

---

### Task 5: Search Presets (Quick-Switch)

**Files:**
- Modify: `db.py` (add `presets` table and methods)
- Modify: `bot.py` (add preset UI handlers)
- Modify: `tests/test_db.py` (add preset tests)

- [ ] **Step 1: Write failing tests for preset DB methods**

Add to `tests/test_db.py`:
```python
def test_presets_table_created(db):
    conn = sqlite3.connect(db.path)
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    names = {t[0] for t in tables}
    assert "presets" in names
    conn.close()


def test_save_and_get_preset(db):
    db.save_preset("user1", "ML Poland", {
        "keywords": "ML Intern,AI Dev",
        "location": "Poland",
        "experience_level": "1",
        "job_type": "2",
    })
    presets = db.get_presets("user1")
    assert len(presets) == 1
    assert presets[0]["name"] == "ML Poland"
    assert presets[0]["location"] == "Poland"


def test_presets_isolated_per_user(db):
    db.save_preset("user1", "Preset A", {"keywords": "ML", "location": "Poland", "experience_level": "1", "job_type": ""})
    db.save_preset("user2", "Preset B", {"keywords": "Data", "location": "Germany", "experience_level": "2", "job_type": "1"})
    assert len(db.get_presets("user1")) == 1
    assert len(db.get_presets("user2")) == 1
    assert db.get_presets("user1")[0]["name"] == "Preset A"


def test_delete_preset(db):
    db.save_preset("user1", "Old", {"keywords": "ML", "location": "Poland", "experience_level": "1", "job_type": ""})
    db.delete_preset("user1", "Old")
    assert len(db.get_presets("user1")) == 0


def test_save_preset_replaces(db):
    db.save_preset("user1", "My Preset", {"keywords": "ML", "location": "Poland", "experience_level": "1", "job_type": ""})
    db.save_preset("user1", "My Preset", {"keywords": "Data", "location": "Germany", "experience_level": "2", "job_type": "1"})
    presets = db.get_presets("user1")
    assert len(presets) == 1
    assert presets[0]["location"] == "Germany"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:\crap\linkedin-jobs-bot && python -m pytest tests/test_db.py::test_presets_table_created -v`
Expected: FAIL — `AssertionError: assert 'presets' in names`

- [ ] **Step 3: Add presets table and methods to `db.py`**

Add to `_migrate()`, after the `saved_jobs` table creation (before `self._conn.commit()`):
```python
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS presets ("
            "  chat_id TEXT NOT NULL,"
            "  name TEXT NOT NULL,"
            "  keywords TEXT,"
            "  location TEXT,"
            "  experience_level TEXT,"
            "  job_type TEXT,"
            "  PRIMARY KEY (chat_id, name)"
            ")"
        )
```

Add methods after `close()` (or before it):
```python
    def save_preset(self, chat_id: str, name: str, data: dict):
        self._conn.execute(
            "INSERT OR REPLACE INTO presets"
            " (chat_id, name, keywords, location, experience_level, job_type)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                chat_id, name,
                data.get("keywords", ""),
                data.get("location", ""),
                data.get("experience_level", ""),
                data.get("job_type", ""),
            ),
        )
        self._conn.commit()

    def get_presets(self, chat_id: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT name, keywords, location, experience_level, job_type"
            " FROM presets WHERE chat_id = ? ORDER BY name",
            (chat_id,),
        ).fetchall()
        return [
            {
                "name": r[0],
                "keywords": r[1],
                "location": r[2],
                "experience_level": r[3],
                "job_type": r[4],
            }
            for r in rows
        ]

    def delete_preset(self, chat_id: str, name: str):
        self._conn.execute(
            "DELETE FROM presets WHERE chat_id = ? AND name = ?",
            (chat_id, name),
        )
        self._conn.commit()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:\crap\linkedin-jobs-bot && python -m pytest tests/test_db.py -v`
Expected: All pass

- [ ] **Step 5: Add preset UI to `bot.py`**

Add a new conversation state (after `WAITING_EXCLUSIONS = 4`):
```python
WAITING_PRESET_NAME = 5
```

Add preset handlers after the exclusions handlers:
```python
async def on_presets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()

    db: JobsDB = context.bot_data["db"]
    chat_id = _get_chat_id(update)
    presets = db.get_presets(chat_id)

    rows = []
    for p in presets:
        rows.append([InlineKeyboardButton(
            f"Load: {p['name']}", callback_data=f"preset_load_{p['name']}"
        )])
    for p in presets:
        rows.append([InlineKeyboardButton(
            f"Delete: {p['name']}", callback_data=f"preset_del_{p['name']}"
        )])
    rows.append([InlineKeyboardButton("Save current as preset", callback_data="preset_save")])
    rows.append([InlineKeyboardButton("Back", callback_data="set_back")])

    text = "<b>Search Presets</b>\n\n"
    if presets:
        for p in presets:
            kw = p["keywords"] or "default"
            loc = p["location"] or "default"
            text += f"<b>{p['name']}</b>: {kw} in {loc}\n"
    else:
        text += "No presets saved yet.\n"
    text += "\nSave your current keywords + settings as a named preset."

    await _send(update, context, text, reply_markup=InlineKeyboardMarkup(rows))


async def on_preset_save_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Send a name for this preset (e.g. <code>ML Poland</code>):\n\nOr /cancel.",
        parse_mode=ParseMode.HTML,
    )
    return WAITING_PRESET_NAME


async def on_preset_name_typed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if not name or len(name) > 30:
        await update.message.reply_text("Name must be 1-30 characters. Try again or /cancel.")
        return WAITING_PRESET_NAME

    db: JobsDB = context.bot_data["db"]
    cfg = context.bot_data
    chat_id = _get_chat_id(update)

    keywords = db.get_keywords(chat_id) or cfg["default_keywords"]
    params = _user_search_params(db, chat_id, cfg)

    db.save_preset(chat_id, name, {
        "keywords": ",".join(keywords),
        "location": params["location"],
        "experience_level": params["experience_level"],
        "job_type": params["job_type"],
    })

    await update.message.reply_text(
        f"Preset <b>{name}</b> saved!",
        parse_mode=ParseMode.HTML,
        reply_markup=_main_menu_keyboard(),
    )
    return ConversationHandler.END


async def on_preset_load(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    name = query.data.removeprefix("preset_load_")
    db: JobsDB = context.bot_data["db"]
    chat_id = _get_chat_id(update)

    presets = db.get_presets(chat_id)
    preset = next((p for p in presets if p["name"] == name), None)
    if not preset:
        await query.edit_message_text("Preset not found.")
        return

    if preset["keywords"]:
        kws = [k.strip() for k in preset["keywords"].split(",") if k.strip()]
        if kws:
            db.set_keywords(chat_id, kws)
    if preset["location"]:
        db.set_preference(chat_id, "location", preset["location"])
    if preset["experience_level"]:
        db.set_preference(chat_id, "experience_level", preset["experience_level"])
    db.set_preference(chat_id, "job_type", preset.get("job_type", ""))

    await query.edit_message_text(
        f"Loaded preset <b>{name}</b>!\n\n"
        f"Keywords: {preset['keywords'] or 'default'}\n"
        f"Location: {preset['location'] or 'default'}\n"
        f"Experience: {_format_exp(preset['experience_level'])}\n"
        f"Job type: {_format_jt(preset.get('job_type', ''))}",
        parse_mode=ParseMode.HTML,
    )
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Menu:",
        reply_markup=_main_menu_keyboard(),
    )


async def on_preset_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    name = query.data.removeprefix("preset_del_")
    db: JobsDB = context.bot_data["db"]
    chat_id = _get_chat_id(update)
    db.delete_preset(chat_id, name)

    await query.edit_message_text(
        f"Preset <b>{name}</b> deleted.",
        parse_mode=ParseMode.HTML,
        reply_markup=_main_menu_keyboard(),
    )
```

- [ ] **Step 6: Add Presets button to settings and register handlers**

In `settings_show()`, add a button (before the Back button):
```python
        [InlineKeyboardButton("Presets", callback_data="cmd_presets")],
```

In `on_menu_button`, add:
```python
    elif data == "cmd_presets":
        await on_presets(update, context)
```

In `main()`, register:
```python
    preset_name_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(on_preset_save_start, pattern="^preset_save$"),
        ],
        states={
            WAITING_PRESET_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, on_preset_name_typed),
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(preset_name_handler)

    app.add_handler(CallbackQueryHandler(on_preset_load, pattern="^preset_load_"))
    app.add_handler(CallbackQueryHandler(on_preset_delete, pattern="^preset_del_"))
    app.add_handler(CallbackQueryHandler(on_presets, pattern="^cmd_presets$"))
```

- [ ] **Step 7: Run all tests**

Run: `cd C:\crap\linkedin-jobs-bot && python -m pytest -v`
Expected: All pass

- [ ] **Step 8: Commit**

```bash
git add db.py bot.py tests/test_db.py
git commit -m "feat: add quick-switch search presets"
```

---

### Task 6: Online/Offline Status & Uptime

**Files:**
- Modify: `bot.py` (startup notification, uptime tracking, status enhancement, shutdown handler)

- [ ] **Step 1: Add uptime and last-scrape tracking to `bot.py`**

In `main()`, after setting `bot_data` keys, add:
```python
    import time as _time
    app.bot_data["start_time"] = _time.time()
    app.bot_data["last_scrape"] = None
    app.bot_data["last_scrape_status"] = None
```

- [ ] **Step 2: Record last scrape time in `check()` and `_scheduled_check()`**

In `check()`, after the `search_jobs(...)` call (after line 152), add:
```python
    import time as _time
    context.bot_data["last_scrape"] = _time.time()
    context.bot_data["last_scrape_status"] = f"{len(new_jobs)} new / {len(all_jobs)} total"
```

In `_scheduled_check()`, after the `search_jobs(...)` call (after line 813), add:
```python
    import time as _time
    context.bot_data["last_scrape"] = _time.time()
    context.bot_data["last_scrape_status"] = f"{len(new_jobs)} new / {len(all_jobs)} total"
```

- [ ] **Step 3: Update `status()` to show uptime and last scrape**

In `status()` (around line 470), add after computing `jt`:
```python
    import time as _time
    from datetime import timedelta

    uptime_secs = int(_time.time() - cfg.get("start_time", _time.time()))
    uptime_str = str(timedelta(seconds=uptime_secs))

    last_scrape = cfg.get("last_scrape")
    if last_scrape:
        ago = int(_time.time() - last_scrape)
        scrape_str = f"{timedelta(seconds=ago)} ago ({cfg.get('last_scrape_status', '')})"
    else:
        scrape_str = "Not yet"
```

Update the status text to include:
```python
        f"<b>Bot status:</b> Online\n"
        f"<b>Uptime:</b> {uptime_str}\n"
        f"<b>Last scrape:</b> {scrape_str}\n"
```

- [ ] **Step 4: Send "Bot online" notification on startup**

In `_restore_subscriptions()` (around line 866), add at the end of the function:
```python
    log = logging.getLogger("linkedin_bot")
    for sub in db.get_subscribers():
        try:
            await app.bot.send_message(
                chat_id=sub["chat_id"],
                text="Bot is now <b>online</b>.",
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            log.warning("Could not send online notification to %s", sub["chat_id"])
```

Note: `_restore_subscriptions` already iterates subscribers, so add this after the existing loop (use a second iteration or save the list).

- [ ] **Step 5: Add graceful shutdown notification**

In `main()`, add a shutdown handler before `app.run_polling()`:
```python
    async def _on_shutdown(app):
        log = logging.getLogger("linkedin_bot")
        log.info("Bot shutting down")
        db: JobsDB = app.bot_data["db"]
        for sub in db.get_subscribers():
            try:
                await app.bot.send_message(
                    chat_id=sub["chat_id"],
                    text="Bot is going <b>offline</b>.",
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                log.warning("Could not send offline notification to %s", sub["chat_id"])

    app.post_shutdown = _on_shutdown
```

- [ ] **Step 6: Run all tests**

Run: `cd C:\crap\linkedin-jobs-bot && python -m pytest -v`
Expected: All pass

- [ ] **Step 7: Commit**

```bash
git add bot.py
git commit -m "feat: add online/offline status notifications and uptime tracking"
```

---

### Task 7: User-Friendly UX (Onboarding, Help, Tips)

**Files:**
- Modify: `bot.py` (improve welcome, add help command, add contextual tips)

- [ ] **Step 1: Improve the welcome message in `start()`**

Replace the `welcome` string in `start()` (around line 101-110) with:
```python
    welcome = (
        f"<b>Welcome to {BOT_NAME}!</b>\n\n"
        "I scan LinkedIn and deliver fresh job offers straight to your chat.\n\n"
        "<b>Get started in 3 steps:</b>\n"
        "1. <b>Keywords</b> — set what roles to search for\n"
        "2. <b>Settings</b> — pick your location, job type, experience\n"
        "3. <b>Search for jobs</b> — get matched offers instantly\n\n"
        "<b>Pro tips:</b>\n"
        "- Use <b>Subscribe</b> to get automatic daily checks\n"
        "- <b>Save</b> interesting offers to review later\n"
        "- Use <b>Presets</b> in Settings to switch between search configs\n"
        "- Set <b>Exclusions</b> to hide jobs with words like 'Senior' or 'Lead'"
    )
```

- [ ] **Step 2: Add Help button to main menu**

In `_main_menu_keyboard()`, add a Help button on the last row (modify around line 60-78):
```python
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
            InlineKeyboardButton("Saved", callback_data="cmd_saved"),
        ],
        [
            InlineKeyboardButton("Unsubscribe", callback_data="cmd_unsubscribe"),
            InlineKeyboardButton("Help", callback_data="cmd_help"),
        ],
    ])
```

- [ ] **Step 3: Add help handler**

Add a `help_show` function:
```python
async def help_show(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()

    text = (
        "<b>Help — LinkedIn Jobs Radar</b>\n\n"
        "<b>Search for jobs</b>\n"
        "Scans LinkedIn with your keywords and settings. "
        "Browse results one by one — save the good ones, skip the rest.\n\n"
        "<b>Keywords</b>\n"
        "Set job titles to search for, separated by commas. "
        "Example: <code>ML Intern, Python Dev, Data Analyst</code>\n\n"
        "<b>Settings</b>\n"
        "Change your search location, experience level, "
        "and job type (remote/hybrid/on-site).\n\n"
        "<b>Presets</b> (in Settings)\n"
        "Save your current keywords + settings as a named preset. "
        "Switch between different search configs instantly.\n\n"
        "<b>Exclusions</b> (in Settings)\n"
        "Hide jobs containing specific words in the title. "
        "Example: <code>Senior, Lead, Manager</code>\n\n"
        "<b>Subscribe</b>\n"
        "Set up automatic checks every 6/12/24h. "
        "New offers are delivered to your chat automatically.\n\n"
        "<b>Saved</b>\n"
        "Browse your saved jobs one by one. "
        "Remove individual jobs or open them on LinkedIn.\n\n"
        "<b>Status</b>\n"
        "View your current settings, subscription status, "
        "bot uptime, and last scrape info.\n\n"
        "<b>Commands:</b>\n"
        "/start — Main menu\n"
        "/help — This help page\n"
        "/check — Quick search\n"
        "/cancel — Cancel current action"
    )
    await _send(update, context, text, reply_markup=_main_menu_keyboard())
```

Register in `on_menu_button`:
```python
    elif data == "cmd_help":
        await help_show(update, context)
```

Register as command in `main()`:
```python
    app.add_handler(CommandHandler("help", help_show))
```

- [ ] **Step 4: Add contextual tips**

In `check()`, after sending the "Found N new offers" message (after line 176), before `_send_next_job`, add a first-time tip:
```python
    if not context.user_data.get("tip_browse_shown"):
        context.user_data["tip_browse_shown"] = True
        await _send(
            update, context,
            "Tip: Use <b>Save</b> to keep offers you like. "
            "Press <b>Back</b> to revisit the previous offer.",
        )
```

In `on_save_job()`, after the saved count increment (after line 326), add:
```python
    if context.user_data.get("saved_count") == 1 and not context.user_data.get("tip_saved_shown"):
        context.user_data["tip_saved_shown"] = True
```

(The tip message is already part of the save confirmation — no extra message needed; just marking the flag for future use.)

After the first `subscribe` confirmation (in `subscribe_button` around line 415, and `subscribe_set` around line 444), add:
```python
    if not context.user_data.get("tip_settings_shown"):
        context.user_data["tip_settings_shown"] = True
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Tip: Use <b>Settings</b> to change your search location, "
            "experience level, and job type for more relevant results.",
            parse_mode=ParseMode.HTML,
        )
```

- [ ] **Step 5: Run all tests**

Run: `cd C:\crap\linkedin-jobs-bot && python -m pytest -v`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add bot.py
git commit -m "feat: improve UX with onboarding, help command, and contextual tips"
```

---

## Final Verification

- [ ] Run the full test suite: `cd C:\crap\linkedin-jobs-bot && python -m pytest -v`
- [ ] Start the bot: `cd C:\crap\linkedin-jobs-bot && python bot.py`
- [ ] Test each feature manually in Telegram:
  1. /start — verify improved welcome message
  2. Search → browse → verify Back button works
  3. Save a job → go to Saved → browse one-by-one → remove one
  4. Settings → Exclusions → set "Senior,Lead" → search → verify filtered
  5. Settings → Presets → save current → change settings → load preset
  6. Status → verify uptime + last scrape shown
  7. /help — verify help text
  8. Check `logs/bot.log` for log entries
  9. Restart bot → verify "online" message sent
