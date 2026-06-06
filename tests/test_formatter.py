from formatter import format_digest, format_single_job


def test_format_single_job_with_salary():
    job = {
        "title": "ML Intern",
        "company": "Google",
        "location": "Kraków (Hybrid)",
        "salary": "$3000/mo",
        "url": "https://linkedin.com/jobs/view/123",
        "posted_at": "2026-06-05",
    }
    text = format_single_job(job, index=1)
    assert "ML Intern" in text
    assert "Google" in text
    assert "$3000/mo" in text
    assert "linkedin.com/jobs/view/123" in text


def test_format_single_job_without_salary():
    job = {
        "title": "AI Intern",
        "company": "Startup",
        "location": "Remote",
        "salary": None,
        "url": "https://linkedin.com/jobs/view/456",
        "posted_at": None,
    }
    text = format_single_job(job, index=2)
    assert "AI Intern" in text
    assert "$" not in text


def test_format_digest_empty():
    text = format_digest([])
    assert "No new jobs" in text


def test_format_digest_with_jobs():
    jobs = [
        {
            "title": "ML Intern",
            "company": "Google",
            "location": "Kraków",
            "salary": None,
            "url": "https://linkedin.com/jobs/view/1",
            "posted_at": "2026-06-05",
        },
        {
            "title": "AI Dev",
            "company": "Meta",
            "location": "Remote",
            "salary": "$4000/mo",
            "url": "https://linkedin.com/jobs/view/2",
            "posted_at": "2026-06-05",
        },
    ]
    text = format_digest(jobs)
    assert "ML Intern" in text
    assert "AI Dev" in text
    assert "Daily Jobs" in text
