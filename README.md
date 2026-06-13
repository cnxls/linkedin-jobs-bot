# LinkedIn Jobs Radar

A Telegram bot that scrapes LinkedIn job listings and delivers them to your chat. You set keywords, filters, and optionally a schedule — the bot handles the rest.

## How it works

1. You send the bot a search request (or it runs on a schedule you set).
2. It calls the Apify LinkedIn Jobs scraper with your keywords, location, experience level, and job type filters.
3. New jobs (ones you haven't seen before) are sent to your Telegram chat one by one.
4. You can save interesting ones and review them later.

## Features

- Search by multiple keywords at once
- Filter by location, experience level (internship to director), and work type (remote, hybrid, on-site)
- Keyword exclusions — hide jobs whose titles contain words like "Senior" or "Lead"
- Subscribe to automatic checks on a custom interval (e.g. every 12 hours)
- Save jobs to a personal list inside the bot
- Presets — save and switch between different search configurations
- Tracks seen jobs per user so you never get the same listing twice

## Requirements

- Python 3.11+
- An [Apify](https://apify.com) account with a token (uses the `curious_coder/linkedin-jobs-scraper` actor)
- A Telegram bot token from [@BotFather](https://t.me/BotFather)

## Setup

1. Clone the repo and install dependencies:

```
pip install -r requirements.txt
```

2. Create a `.env` file in the project root:

```
TELEGRAM_TOKEN=your_telegram_bot_token
APIFY_TOKEN=your_apify_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
```

3. Run the bot:

```
python bot.py
```

The bot creates a local SQLite database (`jobs.db`) on first run to track seen jobs, saved jobs, keywords, and subscriber settings.

## Usage

Start a chat with your bot and send `/start`. The main menu has buttons for everything:

- **Search for jobs** — runs a search right now and shows new results
- **Keywords** — set what roles to search for (e.g. "Python Developer, Backend Engineer")
- **Settings** — change location, experience level, job type, exclusions, and presets
- **Subscribe / Unsubscribe** — enable automatic checks at a set interval
- **Saved** — browse jobs you saved
- **Status** — see your current config and subscription

## Project structure

```
bot.py          main bot logic and Telegram handlers
scraper.py      Apify API call and job parsing
db.py           SQLite wrapper
formatter.py    job card text formatting
logger.py       logging setup
assets/         welcome image
tests/          unit tests
```

## Notes

- The Apify actor costs Apify credits per run. Running searches frequently will use more credits.
- Jobs are filtered by the last 24 hours on LinkedIn's side (`f_TPR=r86400`).
- Each Telegram user has their own seen-jobs history and settings — the bot supports multiple users.
