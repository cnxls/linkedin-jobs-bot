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
