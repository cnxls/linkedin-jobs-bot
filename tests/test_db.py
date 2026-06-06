import os
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
    conn.close()

def test_mark_seen_and_check(db):
    assert not db.is_seen("job123")
    db.mark_seen("job123")
    assert db.is_seen("job123")

def test_mark_seen_idempotent(db):
    db.mark_seen("job123")
    db.mark_seen("job123")
    assert db.is_seen("job123")

def test_get_keywords_returns_defaults_when_empty(db):
    keywords = db.get_keywords()
    assert keywords == []

def test_set_and_get_keywords(db):
    db.set_keywords(["ML Intern", "AI Developer"])
    assert db.get_keywords() == ["ML Intern", "AI Developer"]

def test_set_keywords_replaces(db):
    db.set_keywords(["old keyword"])
    db.set_keywords(["new keyword"])
    assert db.get_keywords() == ["new keyword"]
