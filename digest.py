import asyncio
from telegram import Bot

from db import JobsDB
from scraper import search_jobs
from formatter import format_digest

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

    keywords = db.get_keywords() or default_keywords or []
    all_jobs = search_jobs(apify_token, keywords, DEFAULT_LOCATION, DEFAULT_EXPERIENCE_LEVEL)

    new_jobs = []
    for job in all_jobs:
        if not db.is_seen(job["id"]):
            new_jobs.append(job)
            db.mark_seen(job["id"])

    message = format_digest(new_jobs)

    bot = Bot(token=telegram_token)
    await bot.send_message(chat_id=chat_id, text=message)

    db.close()
    print(f"Sent digest with {len(new_jobs)} new jobs.")


if __name__ == "__main__":
    from config import (
        APIFY_TOKEN,
        TELEGRAM_TOKEN,
        TELEGRAM_CHAT_ID,
        DB_PATH,
        DEFAULT_KEYWORDS,
    )
    asyncio.run(run_digest(
        apify_token=APIFY_TOKEN,
        telegram_token=TELEGRAM_TOKEN,
        chat_id=TELEGRAM_CHAT_ID,
        db_path=DB_PATH,
        default_keywords=DEFAULT_KEYWORDS,
    ))
