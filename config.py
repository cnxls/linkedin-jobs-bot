import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

APIFY_TOKEN = os.environ["APIFY_TOKEN"]
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

DB_PATH = os.path.join(os.path.dirname(__file__), "jobs.db")
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")

DEFAULT_KEYWORDS = [
    "Machine Learning Intern",
    "AI Developer Intern",
    "Python Developer Intern",
    "Data Scientist Intern",
]

DEFAULT_LOCATION = "Poland"
DEFAULT_EXPERIENCE_LEVEL = "1"  # 1 = Internship
