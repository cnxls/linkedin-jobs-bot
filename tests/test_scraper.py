from unittest.mock import MagicMock, patch
from scraper import search_jobs, parse_job_item


def test_parse_job_item_extracts_fields():
    raw = {
        "title": "ML Intern",
        "companyName": "Google",
        "location": "Kraków, Poland",
        "salary": "$3000/mo",
        "url": "https://linkedin.com/jobs/view/123",
        "postedAt": "2026-06-05",
        "description": "We are looking for an ML intern to join our team and work on cutting-edge projects.",
    }
    job = parse_job_item(raw)
    assert job["title"] == "ML Intern"
    assert job["company"] == "Google"
    assert job["location"] == "Kraków, Poland"
    assert job["salary"] == "$3000/mo"
    assert job["url"] == "https://linkedin.com/jobs/view/123"
    assert job["posted_at"] == "2026-06-05"
    assert len(job["id"]) > 0


def test_parse_job_item_handles_missing_salary():
    raw = {
        "title": "AI Intern",
        "companyName": "Startup",
        "location": "Remote",
        "url": "https://linkedin.com/jobs/view/456",
        "postedAt": "2026-06-04",
        "description": "Join us.",
    }
    job = parse_job_item(raw)
    assert job["salary"] is None


def test_parse_job_item_generates_id_from_url():
    raw = {
        "title": "Dev",
        "companyName": "Co",
        "location": "Remote",
        "url": "https://linkedin.com/jobs/view/789",
        "description": "Job.",
    }
    job = parse_job_item(raw)
    assert job["id"] == "789"


@patch("scraper.ApifyClient")
def test_search_jobs_calls_actor_and_returns_parsed(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client

    mock_run = {"defaultDatasetId": "ds123"}
    mock_client.actor.return_value.call.return_value = mock_run
    mock_client.dataset.return_value.iterate_items.return_value = [
        {
            "title": "ML Intern",
            "companyName": "Google",
            "location": "Kraków",
            "url": "https://linkedin.com/jobs/view/111",
            "description": "Great role.",
        }
    ]

    results = search_jobs("test-token", ["ML Intern"], "Poland", "1")
    assert len(results) == 1
    assert results[0]["title"] == "ML Intern"
