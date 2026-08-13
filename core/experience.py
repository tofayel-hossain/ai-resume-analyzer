import calendar
import re
from datetime import datetime

from core.text_utils import normalize_token


MONTHS = {
    name.lower(): i for i, name in enumerate(calendar.month_name) if name
}
MONTHS.update({
    name.lower(): i for i, name in enumerate(calendar.month_abbr) if name
})

DATE_RANGE_RE = re.compile(
    r"(?P<start>(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)?"
    r"\s*['’]?\d{2,4})\s*(?:-|–|—|to)\s*"
    r"(?P<end>present|current|now|(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|"
    r"jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|"
    r"dec(?:ember)?)?\s*['’]?\d{2,4})",
    flags=re.I,
)

YEAR_REQUIREMENT_RE = re.compile(
    r"(?P<years>\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)"
    r"(?:\s+of)?(?:\s+(?:relevant|professional|industry|work))?\s+experience",
    flags=re.I,
)

ROLE_WORDS = {
    "engineer", "developer", "analyst", "scientist", "designer", "manager",
    "administrator", "consultant", "specialist", "architect", "intern",
    "researcher", "lead", "backend", "frontend", "fullstack", "full-stack",
    "software", "data", "machine", "network", "security", "devops",
}


def _parse_date(value: str) -> datetime:
    value = value.strip().lower().replace("’", "").replace("'", "")
    if value in {"present", "current", "now"}:
        return datetime.now()

    m = re.match(r"(?:(\w+)\s+)?(\d{2,4})$", value)
    if not m:
        raise ValueError(value)

    month_token, year_token = m.groups()
    year = int(year_token)
    if year < 100:
        year += 2000 if year < 70 else 1900

    month = 1
    if month_token:
        token = month_token.lower()
        month = MONTHS.get(token, MONTHS.get(token[:3], 1))
    return datetime(year, month, 1)


def _months_between(start: datetime, end: datetime) -> int:
    months = (end.year - start.year) * 12 + (end.month - start.month)
    return max(0, months + 1)


def _merge_intervals(intervals: list[tuple[datetime, datetime]]) -> int:
    if not intervals:
        return 0
    intervals = sorted(intervals, key=lambda x: x[0])
    merged = [list(intervals[0])]
    for start, end in intervals[1:]:
        last = merged[-1]
        if start <= last[1]:
            if end > last[1]:
                last[1] = end
        else:
            merged.append([start, end])
    return sum(_months_between(s, e) for s, e in merged)


def extract_required_years(jd_text: str) -> float | None:
    matches = [float(m.group("years")) for m in YEAR_REQUIREMENT_RE.finditer(jd_text)]
    return max(matches) if matches else None


def _job_role_terms(jd_text: str) -> set[str]:
    top = normalize_token("\n".join(jd_text.splitlines()[:8]))
    tokens = set(top.split())
    return tokens & ROLE_WORDS


def experience_match(resume_text: str, jd_text: str, jd_skills: list[str]) -> dict:
    requirement = extract_required_years(jd_text)
    role_terms = _job_role_terms(jd_text)

    intervals_all = []
    intervals_relevant = []
    evidence = []

    for match in DATE_RANGE_RE.finditer(resume_text):
        try:
            start = _parse_date(match.group("start"))
            end = _parse_date(match.group("end"))
            if end < start:
                continue
        except Exception:
            continue

        intervals_all.append((start, end))

        lo = max(0, match.start() - 300)
        hi = min(len(resume_text), match.end() + 450)
        context = resume_text[lo:hi]
        low_context = normalize_token(context)

        skill_hit = any(skill.lower() in low_context for skill in jd_skills)
        role_hit = any(term in low_context.split() for term in role_terms)

        if skill_hit or role_hit:
            intervals_relevant.append((start, end))
            evidence.append(context.strip()[:260])

    total_months = _merge_intervals(intervals_all)
    relevant_months = _merge_intervals(intervals_relevant)

    # If date ranges exist but we could not confidently classify relevance,
    # keep it conservative rather than inventing relevant years.
    total_years = round(total_months / 12, 1)
    relevant_years = round(relevant_months / 12, 1)

    if requirement is not None:
        if relevant_years > 0:
            score = min(100.0, (relevant_years / requirement) * 100)
        elif total_years > 0:
            score = min(60.0, (total_years / requirement) * 50)
        else:
            score = 25.0
    else:
        if relevant_years >= 3:
            score = 90.0
        elif relevant_years >= 1:
            score = 80.0
        elif total_years > 0:
            score = 65.0
        else:
            score = 50.0

    return {
        "score": round(score, 1),
        "required_years": requirement,
        "total_years_detected": total_years,
        "relevant_years_detected": relevant_years,
        "evidence": evidence[:4],
    }
