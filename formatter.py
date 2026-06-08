import re
from datetime import date
from html import escape

MAX_MESSAGE_LENGTH = 4000

_REQ_HEADING = re.compile(
    r"(?:^|\n)\s*(?:requirements?|qualifications?|what (?:we|you).*?(?:need|look|expect|bring)"
    r"|must[- ]haves?|who you are|skills?\s*(?:&|and)\s*(?:experience|qualifications?)"
    r"|what you.ll need|desired skills|key skills|about you|minimum qualifications"
    r"|basic qualifications|preferred qualifications)\s*:?\s*\n",
    re.IGNORECASE,
)
_BULLET = re.compile(r"^\s*[-•●◦▪*·]\s*", re.MULTILINE)
_NEXT_SECTION = re.compile(
    r"\n\s*(?:responsibilities|benefits|about (?:us|the)|what we offer|perks"
    r"|how to apply|nice[- ]to[- ]have|preferred|bonus|additional|what you.ll (?:do|get)"
    r"|why (?:join|work)|our (?:offer|benefits)|compensation)\s*:?\s*\n",
    re.IGNORECASE,
)


def _extract_requirements(description: str, max_items: int = 6) -> list[str]:
    if not description:
        return []
    m = _REQ_HEADING.search(description)
    if not m:
        return []
    section = description[m.end():]
    next_heading = _NEXT_SECTION.search(section)
    if next_heading:
        section = section[:next_heading.start()]
    lines = _BULLET.split(section)
    if len(lines) <= 1:
        lines = section.strip().split("\n")
    items = []
    for line in lines:
        line = line.strip().split("\n")[0].strip()
        if len(line) > 15:
            if line.endswith("."):
                line = line[:-1]
            items.append(line)
        if len(items) >= max_items:
            break
    return items


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

    reqs = _extract_requirements(job.get("description", ""))
    if reqs:
        req_text = "\n".join(f"· {escape(r)}" for r in reqs)
        lines.append(f"\n<blockquote>{req_text}</blockquote>")

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
