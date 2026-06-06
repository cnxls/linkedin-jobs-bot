import hashlib
from apify_client import ApifyClient

ACTOR_ID = "bebity/linkedin-jobs-scraper"


def parse_job_item(raw: dict) -> dict:
    url = raw.get("url", "")
    job_id = url.rstrip("/").split("/")[-1] if url else hashlib.md5(
        f"{raw.get('title', '')}{raw.get('companyName', '')}".encode()
    ).hexdigest()

    return {
        "id": job_id,
        "title": raw.get("title", "Unknown"),
        "company": raw.get("companyName", "Unknown"),
        "location": raw.get("location", "Unknown"),
        "salary": raw.get("salary") or None,
        "url": url,
        "posted_at": raw.get("postedAt"),
        "description": raw.get("description", ""),
    }


def search_jobs(
    apify_token: str,
    keywords: list[str],
    location: str,
    experience_level: str,
) -> list[dict]:
    client = ApifyClient(apify_token)

    all_jobs = []
    for keyword in keywords:
        run_input = {
            "searchKeyword": keyword,
            "locationSearch": location,
            "experienceLevel": experience_level,
            "publishedAt": "past 24 hours",
            "rows": 25,
        }

        run = client.actor(ACTOR_ID).call(
            run_input=run_input,
            timeout_secs=120,
        )

        if run and run.get("defaultDatasetId"):
            for item in client.dataset(run["defaultDatasetId"]).iterate_items():
                all_jobs.append(parse_job_item(item))

    return all_jobs
