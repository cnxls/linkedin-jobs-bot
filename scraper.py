import hashlib
import logging
from urllib.parse import quote_plus

from apify_client import ApifyClient

log = logging.getLogger("linkedin_bot")

ACTOR_ID = "curious_coder/linkedin-jobs-scraper"


def build_linkedin_search_url(
    keyword: str,
    location: str,
    experience_level: str,
    job_type: str = "",
) -> str:
    url = (
        f"https://www.linkedin.com/jobs/search/?"
        f"keywords={quote_plus(keyword)}"
        f"&location={quote_plus(location)}"
        f"&f_TPR=r86400"
    )
    if experience_level:
        for code in experience_level.split(","):
            code = code.strip()
            if code:
                url += f"&f_E={code}"
    if job_type:
        for code in job_type.split(","):
            code = code.strip()
            if code:
                url += f"&f_WT={code}"
    return url


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
        "salary": raw.get("salary") or (", ".join(raw["salaryInfo"]) if raw.get("salaryInfo") else None),
        "url": url,
        "posted_at": raw.get("postedAt") or raw.get("publishedAt"),
        "description": raw.get("descriptionText") or raw.get("description") or "",
    }


def search_jobs(
    apify_token: str,
    keywords: list[str],
    location: str,
    experience_level: str,
    job_type: str = "",
) -> list[dict]:
    client = ApifyClient(apify_token)

    urls = [
        build_linkedin_search_url(kw, location, experience_level, job_type)
        for kw in keywords
    ]

    run_input = {
        "urls": urls,
        "count": 25,
        "scrapeCompany": False,
    }

    log.info("Starting Apify scrape: %d keywords, location=%s", len(keywords), location)

    try:
        run = client.actor(ACTOR_ID).call(run_input=run_input)
    except Exception:
        log.exception("Apify actor call failed")
        return []

    all_jobs = []
    dataset_id = getattr(run, "default_dataset_id", None) or (run.get("defaultDatasetId") if isinstance(run, dict) else None)
    if dataset_id:
        for item in client.dataset(dataset_id).iterate_items():
            all_jobs.append(parse_job_item(item))

    log.info("Scrape complete: %d jobs found", len(all_jobs))

    if len(all_jobs) == 0:
        log.warning("Scraper returned 0 results — possible LinkedIn block or bad query")

    return all_jobs
