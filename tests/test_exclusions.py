from bot import _filter_excluded


def test_filter_excluded_removes_matching():
    jobs = [
        {"id": "1", "title": "Senior ML Engineer"},
        {"id": "2", "title": "ML Intern"},
        {"id": "3", "title": "Lead Developer"},
        {"id": "4", "title": "Junior Python Dev"},
    ]
    filtered = _filter_excluded(jobs, "Senior,Lead")
    assert len(filtered) == 2
    assert filtered[0]["id"] == "2"
    assert filtered[1]["id"] == "4"


def test_filter_excluded_case_insensitive():
    jobs = [
        {"id": "1", "title": "senior ml engineer"},
        {"id": "2", "title": "ML Intern"},
    ]
    filtered = _filter_excluded(jobs, "Senior")
    assert len(filtered) == 1
    assert filtered[0]["id"] == "2"


def test_filter_excluded_empty_exclusions():
    jobs = [{"id": "1", "title": "ML Intern"}]
    assert _filter_excluded(jobs, "") == jobs
    assert _filter_excluded(jobs, None) == jobs
