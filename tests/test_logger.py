import os
import logging
import pytest


@pytest.fixture(autouse=True)
def reset_logger_global():
    """Reset the module-level _logger global and remove any existing handlers
    between tests so each test starts with a clean slate."""
    import logger as logger_mod
    # Reset the global before the test
    logger_mod._logger = None
    # Also clear any handlers from the 'linkedin_bot' logger so handlers
    # don't accumulate across tests
    existing = logging.getLogger("linkedin_bot")
    existing.handlers.clear()
    yield
    # Reset again after the test
    logger_mod._logger = None
    existing = logging.getLogger("linkedin_bot")
    existing.handlers.clear()


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
    with open(os.path.join(log_dir, log_files[0]), encoding="utf-8") as f:
        content = f.read()
    assert "test message" in content


def test_setup_logging_idempotent(tmp_path):
    log_dir = str(tmp_path / "logs")
    from logger import setup_logging
    log1 = setup_logging(log_dir)
    log2 = setup_logging(log_dir)
    assert log1 is log2
