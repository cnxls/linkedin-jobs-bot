from datetime import date
from html import escape

MAX_MESSAGE_LENGTH = 4000


def format_single_job(job: dict, index: int) -> str:
    title = escape(job.get("title", "Unknown"))
    company = escape(job.get("company", "Unknown"))
    location = escape(job.get("location", "Unknown"))
    url = job.get("url", "")

    lines = [f"<b>{title}</b>"]
    lines.append(f"{company}  ·  {location}")

    details = []
    if job.get("salary"):
        details.append(f"<b>{escape(job['salary'])}</b>")
    if job.get("posted_at"):
        details.append(escape(job["posted_at"]))
    if details:
        lines.append(" | ".join(details))

    if url:
        lines.append(f'<a href="{url}">View on LinkedIn</a>')

    return "\n".join(lines)


def format_job_card(job: dict, index: int, total: int) -> str:
    header = f"Offer {index}/{total}\n\n"
    return header + format_single_job(job, index)


def format_digest(jobs: list[dict]) -> str:
    if not jobs:
        return "No new jobs found today."

    header = f"Daily Jobs — {date.today().strftime('%B %d')}\n"
    body = "\n\n".join(
        format_single_job(job, i + 1) for i, job in enumerate(jobs)
    )
    return f"{header}\n{body}"


def format_digest_chunks(jobs: list[dict]) -> list[str]:
    if not jobs:
        return ["No new jobs found today."]

    header = f"Daily Jobs — {date.today().strftime('%B %d')} ({len(jobs)} new)\n\n"
    chunks = []
    current = header

    for i, job in enumerate(jobs):
        entry = format_single_job(job, i + 1)
        if len(current) + len(entry) + 2 > MAX_MESSAGE_LENGTH:
            chunks.append(current)
            current = ""
        current += entry + "\n\n"

    if current.strip():
        chunks.append(current)

    return chunks
