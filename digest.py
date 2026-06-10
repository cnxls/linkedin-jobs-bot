import asyncio
import logging
from telegram import Bot
from telegram.constants import ParseMode

from db import JobsDB
from scraper import search_jobs
from formatter import format_digest

log = logging.getLogger("linkedin_bot")

DEFAULT_LOCATION = "Poland"
DEFAULT_EXPERIENCE_LEVEL = "1"


async def run_digest(
    apify_token: str,
    telegram_token: str,
    chat_id: str,
    db_path: str,
    default_keywords: list[str] | None = None,
):
    db = JobsDB(db_path)

    keywords = db.get_keywords(chat_id) or default_keywords or []
    prefs = db.get_all_preferences(chat_id)
    location = prefs.get("location", DEFAULT_LOCATION)
    experience_level = prefs.get("experience_level", DEFAULT_EXPERIENCE_LEVEL)
    job_type = prefs.get("job_type", "")
    all_jobs = search_jobs(apify_token, keywords, location, experience_level, job_type)

    new_jobs = []
    for job in all_jobs:
        if not db.is_seen(chat_id, job["id"]):
            new_jobs.append(job)
            db.mark_seen(chat_id, job["id"])

    message = format_digest(new_jobs)

    bot = Bot(token=telegram_token)
    await bot.send_message(chat_id=chat_id, text=message, parse_mode=ParseMode.HTML)

    db.close()
    log.info("Digest sent to %s: %d new jobs", chat_id, len(new_jobs))


if __name__ == "__main__":
    from config import (
        APIFY_TOKEN,
        TELEGRAM_TOKEN,
        TELEGRAM_CHAT_ID,
        DB_PATH,
        DEFAULT_KEYWORDS,
        LOG_DIR,
    )
    from logger import setup_logging
    setup_logging(LOG_DIR)
    asyncio.run(run_digest(
        apify_token=APIFY_TOKEN,
        telegram_token=TELEGRAM_TOKEN,
        chat_id=TELEGRAM_CHAT_ID,
        db_path=DB_PATH,
        default_keywords=DEFAULT_KEYWORDS,
    ))
