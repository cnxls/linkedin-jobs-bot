import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from digest import run_digest


def test_run_digest_sends_new_jobs():
    with patch("digest.search_jobs") as mock_search, \
         patch("digest.Bot") as mock_bot_cls, \
         patch("digest.JobsDB") as mock_db_cls:

        mock_db = MagicMock()
        mock_db_cls.return_value = mock_db
        mock_db.get_keywords.return_value = ["ML Intern"]
        mock_db.mark_seen_if_new.return_value = True

        mock_search.return_value = [
            {
                "id": "job456",
                "title": "ML Intern",
                "company": "Google",
                "location": "Kraków",
                "salary": None,
                "url": "https://linkedin.com/jobs/view/456",
                "posted_at": "2026-06-05",
            }
        ]

        mock_bot = AsyncMock()
        mock_bot_cls.return_value = mock_bot

        asyncio.run(run_digest(
            apify_token="test",
            telegram_token="test",
            chat_id="123",
            db_path=":memory:",
        ))

        mock_bot.send_message.assert_called_once()
        mock_db.mark_seen_if_new.assert_called_with("123", "job456")


def test_run_digest_skips_seen_jobs():
    with patch("digest.search_jobs") as mock_search, \
         patch("digest.Bot") as mock_bot_cls, \
         patch("digest.JobsDB") as mock_db_cls:

        mock_db = MagicMock()
        mock_db_cls.return_value = mock_db
        mock_db.get_keywords.return_value = ["ML Intern"]
        mock_db.mark_seen_if_new.return_value = False

        mock_search.return_value = [
            {
                "id": "job456",
                "title": "ML Intern",
                "company": "Google",
                "location": "Kraków",
                "salary": None,
                "url": "https://linkedin.com/jobs/view/456",
                "posted_at": "2026-06-05",
            }
        ]

        mock_bot = AsyncMock()
        mock_bot_cls.return_value = mock_bot

        asyncio.run(run_digest(
            apify_token="test",
            telegram_token="test",
            chat_id="123",
            db_path=":memory:",
        ))

        args = mock_bot.send_message.call_args
        assert "No new jobs" in args[1]["text"]
