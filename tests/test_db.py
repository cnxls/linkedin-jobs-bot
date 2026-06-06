import sqlite3
import pytest
from db import JobsDB


@pytest.fixture
def db(tmp_path):
    path = str(tmp_path / "test.db")
    return JobsDB(path)


def test_tables_created(db):
    conn = sqlite3.connect(db.path)
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    names = {t[0] for t in tables}
    assert "seen_jobs" in names
    assert "keywords" in names
    assert "subscribers" in names
    conn.close()


def test_mark_seen_and_check(db):
    assert not db.is_seen("user1", "job123")
    db.mark_seen("user1", "job123")
    assert db.is_seen("user1", "job123")


def test_seen_jobs_isolated_per_user(db):
    db.mark_seen("user1", "job123")
    assert not db.is_seen("user2", "job123")


def test_mark_seen_idempotent(db):
    db.mark_seen("user1", "job123")
    db.mark_seen("user1", "job123")
    assert db.is_seen("user1", "job123")


def test_get_keywords_returns_empty_when_none(db):
    assert db.get_keywords("user1") == []


def test_set_and_get_keywords(db):
    db.set_keywords("user1", ["ML Intern", "AI Developer"])
    assert db.get_keywords("user1") == ["ML Intern", "AI Developer"]


def test_keywords_isolated_per_user(db):
    db.set_keywords("user1", ["ML Intern"])
    db.set_keywords("user2", ["Data Analyst"])
    assert db.get_keywords("user1") == ["ML Intern"]
    assert db.get_keywords("user2") == ["Data Analyst"]


def test_set_keywords_replaces(db):
    db.set_keywords("user1", ["old keyword"])
    db.set_keywords("user1", ["new keyword"])
    assert db.get_keywords("user1") == ["new keyword"]


def test_subscribe_and_check(db):
    assert not db.is_subscribed("user1")
    db.subscribe("user1", 12)
    assert db.is_subscribed("user1")


def test_unsubscribe(db):
    db.subscribe("user1", 24)
    db.unsubscribe("user1")
    assert not db.is_subscribed("user1")


def test_get_subscribers(db):
    db.subscribe("user1", 6)
    db.subscribe("user2", 24)
    subs = db.get_subscribers()
    assert len(subs) == 2
    chat_ids = {s["chat_id"] for s in subs}
    assert chat_ids == {"user1", "user2"}


def test_preferences_table_created(db):
    conn = sqlite3.connect(db.path)
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    names = {t[0] for t in tables}
    assert "preferences" in names
    conn.close()


def test_set_and_get_preference(db):
    assert db.get_preference("user1", "location") is None
    db.set_preference("user1", "location", "Kraków")
    assert db.get_preference("user1", "location") == "Kraków"


def test_preferences_isolated_per_user(db):
    db.set_preference("user1", "location", "Kraków")
    db.set_preference("user2", "location", "Warsaw")
    assert db.get_preference("user1", "location") == "Kraków"
    assert db.get_preference("user2", "location") == "Warsaw"


def test_preferences_isolated_per_key(db):
    db.set_preference("user1", "location", "Kraków")
    db.set_preference("user1", "job_type", "2")
    assert db.get_preference("user1", "location") == "Kraków"
    assert db.get_preference("user1", "job_type") == "2"


def test_set_preference_replaces(db):
    db.set_preference("user1", "location", "Kraków")
    db.set_preference("user1", "location", "Berlin")
    assert db.get_preference("user1", "location") == "Berlin"


def test_get_all_preferences(db):
    db.set_preference("user1", "location", "Kraków")
    db.set_preference("user1", "experience_level", "1,2")
    db.set_preference("user1", "job_type", "2")
    prefs = db.get_all_preferences("user1")
    assert prefs == {"location": "Kraków", "experience_level": "1,2", "job_type": "2"}


def test_get_all_preferences_isolated(db):
    db.set_preference("user1", "location", "Kraków")
    db.set_preference("user2", "location", "Berlin")
    db.set_preference("user2", "job_type", "1")
    assert db.get_all_preferences("user1") == {"location": "Kraków"}
    assert db.get_all_preferences("user2") == {"location": "Berlin", "job_type": "1"}


def test_get_all_preferences_empty(db):
    assert db.get_all_preferences("user1") == {}


def test_full_multiuser_isolation(db):
    db.set_keywords("user1", ["ML Intern"])
    db.set_keywords("user2", ["Data Analyst"])
    db.set_preference("user1", "location", "Kraków")
    db.set_preference("user1", "experience_level", "1")
    db.set_preference("user2", "location", "Berlin")
    db.set_preference("user2", "experience_level", "2")
    db.set_preference("user2", "job_type", "2")
    db.mark_seen("user1", "job100")
    db.mark_seen("user2", "job200")
    db.subscribe("user1", 12)

    assert db.get_keywords("user1") == ["ML Intern"]
    assert db.get_keywords("user2") == ["Data Analyst"]
    assert db.get_all_preferences("user1") == {"location": "Kraków", "experience_level": "1"}
    assert db.get_all_preferences("user2") == {"location": "Berlin", "experience_level": "2", "job_type": "2"}
    assert db.is_seen("user1", "job100")
    assert not db.is_seen("user1", "job200")
    assert not db.is_seen("user2", "job100")
    assert db.is_seen("user2", "job200")
    assert db.is_subscribed("user1")
    assert not db.is_subscribed("user2")
