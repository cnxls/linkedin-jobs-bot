from datetime import date

MAX_MESSAGE_LENGTH = 4000


def format_single_job(job: dict, index: int) -> str:
    lines = [f"{index}. {job['title']} — {job['company']} — {job['location']}"]

    details = []
    if job.get("salary"):
        details.append(job["salary"])
    if job.get("posted_at"):
        details.append(f"Posted {job['posted_at']}")
    if details:
        lines.append(f"   {' | '.join(details)}")

    lines.append(f"   {job['url']}")
    return "\n".join(lines)


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
