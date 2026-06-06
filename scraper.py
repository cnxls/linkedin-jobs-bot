import hashlib
from urllib.parse import quote_plus

from apify_client import ApifyClient

ACTOR_ID = "curious_coder/linkedin-jobs-scraper"


def build_linkedin_search_url(keyword: str, location: str, experience_level: str) -> str:
    # f_E=1 is Internship, f_TPR=r86400 is past 24 hours
    return (
        f"https://www.linkedin.com/jobs/search/?"
        f"keywords={quote_plus(keyword)}"
        f"&location={quote_plus(location)}"
        f"&f_E={experience_level}"
        f"&f_TPR=r86400"
    )


def parse_job_item(raw: dict) -> dict:
    url = raw.get("url") or raw.get("jobUrl") or raw.get("link") or ""
    job_id = url.rstrip("/").split("/")[-1] if url else hashlib.md5(
        f"{raw.get('title', '')}{raw.get('companyName', '')}".encode()
    ).hexdigest()

    return {
        "id": job_id,
        "title": raw.get("title", "Unknown"),
        "company": raw.get("companyName") or raw.get("company", "Unknown"),
        "location": raw.get("location", "Unknown"),
        "salary": raw.get("salary") or None,
        "url": url,
        "posted_at": raw.get("postedAt") or raw.get("publishedAt"),
        "description": raw.get("description", ""),
    }


def search_jobs(
    apify_token: str,
    keywords: list[str],
    location: str,
    experience_level: str,
) -> list[dict]:
    client = ApifyClient(apify_token)

    urls = [
        build_linkedin_search_url(kw, location, experience_level)
        for kw in keywords
    ]

    run_input = {
        "urls": urls,
        "count": 25,
        "scrapeCompany": False,
    }

    run = client.actor(ACTOR_ID).call(run_input=run_input)

    all_jobs = []
    dataset_id = getattr(run, "default_dataset_id", None) or (run.get("defaultDatasetId") if isinstance(run, dict) else None)
    if dataset_id:
        for item in client.dataset(dataset_id).iterate_items():
            all_jobs.append(parse_job_item(item))

    return all_jobs
