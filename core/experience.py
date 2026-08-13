import calendar
import re
from datetime import datetime

from core.text_utils import SECTION_ALIASES, normalize_token
from core.requirements_matcher import match_experience_domain_requirements


MONTHS = {name.lower(): i for i, name in enumerate(calendar.month_name) if name}
MONTHS.update({name.lower(): i for i, name in enumerate(calendar.month_abbr) if name})

NUMBER_WORDS = {
    "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
    "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
    "eleven": "11", "twelve": "12", "thirteen": "13", "fourteen": "14",
    "fifteen": "15",
}

MONTH_WORD = (
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
)

# Supports: Jan 2022, January 2022, 01/2022, 2022/01, 2022-01, 2022.
DATE_TOKEN = rf"(?:{MONTH_WORD}\s+['’]?\d{{2,4}}|\d{{4}}[./-]\d{{1,2}}|\d{{1,2}}[./-]\d{{2,4}}|\d{{4}})"
DATE_RANGE_RE = re.compile(
    rf"(?P<start>{DATE_TOKEN})\s*(?:-|–|—|to|until|through)\s*"
    rf"(?P<end>present|current|now|today|{DATE_TOKEN})",
    flags=re.I,
)

YEAR_EXPR_RE = re.compile(
    r"(?P<min>\d+(?:\.\d+)?)\s*(?P<plus>\+|plus)?\s*"
    r"(?:(?:-|–|—|to)\s*(?P<max>\d+(?:\.\d+)?)\s*)?"
    r"(?:years?|yrs?)\b",
    flags=re.I,
)

REQUIREMENT_CUES = {
    "minimum", "at least", "required", "requirement", "requirements", "must have",
    "should have", "need", "needs", "needed", "looking for", "qualification",
    "qualifications", "eligible", "with", "more than", "over",
}
EXPERIENCE_CUES = {
    "experience", "experienced", "professional", "relevant", "work", "working",
    "industry", "hands-on", "hands on", "background", "development", "engineering",
    "programming", "software", "backend", "front-end", "frontend", "full-stack",
    "fullstack", "data", "devops", "technical",
}
PREFERRED_CUES = {"preferred", "desirable", "nice to have", "bonus", "plus"}
EDUCATION_CUES = {"degree", "bachelor", "bachelors", "master", "masters", "university", "college", "education", "program"}

ROLE_WORDS = {
    "engineer", "developer", "analyst", "scientist", "designer", "manager",
    "administrator", "consultant", "specialist", "architect", "intern",
    "researcher", "lead", "backend", "frontend", "front-end", "fullstack",
    "full-stack", "software", "data", "machine", "network", "security", "devops",
    "qa", "tester", "testing", "accountant", "accounting", "finance", "financial",
    "marketing", "sales", "product", "project", "operations", "support", "cloud",
    "mobile", "web", "database", "systems", "system",
}
GENERIC_ROLE_WORDS = {"engineer", "developer", "analyst", "manager", "specialist", "lead", "intern", "consultant"}

WORK_CUES = ROLE_WORDS | {
    "company", "technologies", "technology", "solutions", "limited", "ltd", "inc",
    "corp", "corporation", "responsibilities", "responsibility", "achievement",
    "achievements", "employment", "worked", "developed", "built", "managed",
    "implemented", "designed", "maintained", "deployed",
}


def _replace_number_words(text: str) -> str:
    out = text
    for word, number in NUMBER_WORDS.items():
        out = re.sub(rf"\b{word}\b", number, out, flags=re.I)
    return out


def _context_score(context: str) -> int:
    low = normalize_token(context)
    score = 0

    if "experience" in low:
        score += 5
    if any(cue in low for cue in REQUIREMENT_CUES):
        score += 2
    if any(cue in low for cue in EXPERIENCE_CUES):
        score += 2
    if any(cue in low for cue in PREFERRED_CUES):
        score -= 2
    if any(cue in low for cue in EDUCATION_CUES) and "experience" not in low:
        score -= 5

    return score


JD_SECTION_HEADINGS = {
    "education",
    "experience",
    "additional requirements",
    "responsibilities & context",
    "responsibilities",
    "skills & expertise",
    "skills and expertise",
    "other relevant skills",
    "compensation & other benefits",
    "compensation and other benefits",
    "workplace",
    "employment status",
    "job location",
}

def _normalize_heading_text(line: str) -> str:
    cleaned = line.lower().replace("&", "and").strip().rstrip(":")
    cleaned = re.sub(r"[^a-z0-9 +#./-]", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _extract_jd_section(jd_text: str, heading_names: set[str]) -> tuple[str, bool]:
    """Return text under one of the requested JD headings until the next known heading."""
    normalized_targets = {_normalize_heading_text(x) for x in heading_names}
    normalized_headings = {_normalize_heading_text(x) for x in JD_SECTION_HEADINGS}

    lines = jd_text.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    start = None
    for i, line in enumerate(lines):
        if _normalize_heading_text(line) in normalized_targets:
            start = i + 1
            break

    if start is None:
        return "", False

    end = len(lines)
    for i in range(start, len(lines)):
        heading = _normalize_heading_text(lines[i])
        if heading in normalized_headings:
            end = i
            break

    return "\n".join(lines[start:end]).strip(), True


def extract_required_years(jd_text: str) -> float | None:
    """Return the minimum required experience in years."""
    return extract_requirement_details(jd_text)["years"]


def extract_requirement_details(jd_text: str) -> dict:
    """
    Detect experience requirements including standalone values inside an Experience section.

    Examples:
      - Experience / 4 to 5 years
      - 4-5 years
      - 3+ years of experience
      - minimum 3 years
      - at least three years
      - experience of at least 4 years
    """
    text = _replace_number_words(jd_text.replace("\u00a0", " "))

    # Highest-confidence path: a dedicated "Experience" section.
    experience_section, found_section = _extract_jd_section(text, {"experience"})
    section_candidates = []
    if found_section:
        for match in YEAR_EXPR_RE.finditer(experience_section):
            minimum = float(match.group("min"))
            maximum = float(match.group("max")) if match.group("max") else None
            section_candidates.append({
                "years": minimum,
                "max_years": maximum,
                "score": 100,
                "text": match.group(0).strip(),
                "span": (match.start(), match.end()),
                "source": "Experience section",
            })

    if section_candidates:
        # The first explicit numeric range in the Experience section is normally the job requirement.
        best = section_candidates[0]
        return {
            "years": best["years"],
            "max_years": best["max_years"],
            "text": best["text"],
            "source": best["source"],
            "candidates": section_candidates[:5],
        }

    # Fallback: scan the full JD using context around each year expression.
    candidates = []
    for match in YEAR_EXPR_RE.finditer(text):
        lo = max(0, match.start() - 130)
        hi = min(len(text), match.end() + 160)
        context = text[lo:hi].replace("\n", " ")
        score = _context_score(context)

        after = text[match.end(): min(len(text), match.end() + 110)]
        before = text[max(0, match.start() - 110): match.start()]

        if re.search(r"\bexperience\b", after, flags=re.I) or re.search(r"\bexperience\b", before, flags=re.I):
            score += 4

        if re.search(
            r"\b(?:minimum|at\s+least|required|must\s+have|should\s+have|applicants?\s+should\s+have)\b",
            context,
            flags=re.I,
        ):
            score += 3

        if score < 3:
            continue

        minimum = float(match.group("min"))
        maximum = float(match.group("max")) if match.group("max") else None
        candidates.append({
            "years": minimum,
            "max_years": maximum,
            "score": score,
            "text": context.strip(),
            "span": (match.start(), match.end()),
            "source": "JD context",
        })

    if not candidates:
        return {
            "years": None,
            "max_years": None,
            "text": None,
            "source": None,
            "candidates": [],
        }

    candidates.sort(key=lambda item: (-item["score"], item["span"][0]))
    best = candidates[0]
    return {
        "years": best["years"],
        "max_years": best["max_years"],
        "text": best["text"],
        "source": best["source"],
        "candidates": candidates[:5],
    }


def _parse_date(value: str, *, is_end: bool = False) -> datetime:
    value = value.strip().lower().replace("’", "").replace("'", "")
    if value in {"present", "current", "now", "today"}:
        return datetime.now()

    # Month name + year, e.g. Jan 2022.
    month_name_match = re.fullmatch(r"([a-z]+)\s+(\d{2,4})", value)
    if month_name_match:
        month_token, year_token = month_name_match.groups()
        year = int(year_token)
        if year < 100:
            year += 2000 if year < 70 else 1900
        month = MONTHS.get(month_token, MONTHS.get(month_token[:3], 1))
        return datetime(year, month, 1)

    # Numeric month/year or year/month.
    numeric_match = re.fullmatch(r"(\d{1,4})[./-](\d{1,4})", value)
    if numeric_match:
        a, b = (int(x) for x in numeric_match.groups())
        if a >= 1000:  # YYYY/MM
            year, month = a, b
        else:  # MM/YYYY
            month, year = a, b
        if year < 100:
            year += 2000 if year < 70 else 1900
        if not 1 <= month <= 12:
            raise ValueError(value)
        return datetime(year, month, 1)

    # Year only. Treat an ending year as December so 2022-2024 is about 3 years.
    if re.fullmatch(r"\d{2,4}", value):
        year = int(value)
        if year < 100:
            year += 2000 if year < 70 else 1900
        return datetime(year, 12 if is_end else 1, 1)

    raise ValueError(value)


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
    return sum(_months_between(start, end) for start, end in merged)


def _heading_matches(line: str, aliases: list[str]) -> bool:
    cleaned = re.sub(r"[^a-z0-9&/ +#.-]", "", line.lower()).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    if len(cleaned) > 70:
        return False
    return any(cleaned == alias or cleaned.startswith(alias + " ") for alias in aliases)


def extract_experience_section(resume_text: str) -> tuple[str, bool]:
    """Extract the Work Experience section when a recognizable heading exists."""
    lines = resume_text.splitlines()
    experience_aliases = SECTION_ALIASES.get("experience", [])

    start = None
    for index, line in enumerate(lines):
        if _heading_matches(line, experience_aliases):
            start = index + 1
            break

    if start is None:
        return resume_text, False

    other_aliases = []
    for section, aliases in SECTION_ALIASES.items():
        if section != "experience":
            other_aliases.extend(aliases)

    end = len(lines)
    for index in range(start, len(lines)):
        if _heading_matches(lines[index], other_aliases):
            end = index
            break

    section_text = "\n".join(lines[start:end]).strip()
    if not section_text:
        return resume_text, False
    return section_text, True


def _job_role_terms(jd_text: str) -> set[str]:
    normalized = normalize_token(jd_text)
    tokens = set(normalized.split())
    return tokens & ROLE_WORDS


RELEVANCE_STOPWORDS = {
    "about", "above", "added", "additional", "advantage", "applicant", "applicants",
    "area", "areas", "basic", "candidate", "candidates", "company", "context",
    "duty", "duties", "emergency", "experience", "experienced", "following",
    "full", "good", "have", "having", "knowledge", "management", "other", "others",
    "requirement", "requirements", "responsibilities", "responsibility", "role",
    "should", "skill", "skills", "support", "team", "teammate", "work", "working",
    "year", "years", "with", "from", "their", "this", "that", "will", "would",
    "and", "the", "for", "are", "but", "not", "all", "any", "per", "etc",
    "order", "when", "more", "only", "than", "like", "such", "into", "your",
    "our", "his", "her", "its", "they", "them", "as", "at", "on", "in", "of",
    "to", "by", "or", "an", "a", "is", "be",
}

# Important domain words are intentionally not software-specific.
# These make relevance detection work for EEE, telecom, mechanical, data-center,
# operations, business and other technical job descriptions too.
GENERIC_DOMAIN_TERMS = {
    "electrical", "electronics", "mechanical", "telecommunication", "telecom",
    "datacenter", "data", "centre", "center", "noc", "operation", "operations",
    "maintenance", "commissioning", "testing", "ups", "generator", "diesel",
    "fire", "protection", "detection", "pfi", "panel", "hvac", "bms", "power",
    "wiring", "server", "router", "switch", "network", "hardware", "inventory",
    "engineering", "engineer", "technical", "installation", "equipment",
    "production", "quality", "manufacturing", "sales", "marketing", "finance",
    "accounting", "project", "design", "development", "cloud", "database",
}


def _jd_relevance_text(jd_text: str) -> str:
    """
    Build relevance text from JD content sections while ignoring benefits/location.
    Handles nested headings such as:
        Responsibilities & Context
        Responsibilities:
    """
    relevant_starts = {
        "responsibilities and context",
        "responsibilities",
        "skills and expertise",
        "other relevant skills",
        "additional requirements",
    }
    hard_stops = {
        "compensation and other benefits",
        "workplace",
        "employment status",
        "job location",
    }

    lines = jd_text.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    collected = []
    capture = False

    for line in lines:
        heading = _normalize_heading_text(line)

        if heading in hard_stops:
            capture = False
            continue

        if heading in relevant_starts:
            capture = True
            continue

        # Other known headings end the current relevance section unless they are
        # one of the nested/related relevance headings above.
        if heading in {_normalize_heading_text(x) for x in JD_SECTION_HEADINGS}:
            if capture:
                capture = False
            continue

        if capture and line.strip():
            collected.append(line.strip())

    if collected:
        return "\n".join(collected)

    return jd_text


def _jd_domain_terms(jd_text: str) -> set[str]:
    relevant_text = normalize_token(_jd_relevance_text(jd_text))
    tokens = re.findall(r"[a-z][a-z0-9+#./-]{2,}", relevant_text)

    # Keep distinctive content words. Also retain known cross-domain technical terms.
    terms = {
        token for token in tokens
        if token not in RELEVANCE_STOPWORDS and (len(token) >= 4 or token in {"ups", "noc", "bms", "pfi"})
    }
    return terms | (set(tokens) & GENERIC_DOMAIN_TERMS)


def _lexical_similarity(block: str, jd_relevance_text: str) -> float:
    """Small TF-IDF similarity used only as supporting relevance evidence."""
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        vectorizer = TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2),
            max_features=2500,
        )
        matrix = vectorizer.fit_transform([block, jd_relevance_text])
        return float(cosine_similarity(matrix[0:1], matrix[1:2])[0][0])
    except Exception:
        return 0.0


def _date_matches_with_blocks(section_text: str) -> list[dict]:
    """Create a local employment block around every detected date range."""
    lines = section_text.splitlines()
    line_offsets = []
    cursor = 0
    for line in lines:
        line_offsets.append(cursor)
        cursor += len(line) + 1

    matches = []
    for match in DATE_RANGE_RE.finditer(section_text):
        line_index = 0
        for i, offset in enumerate(line_offsets):
            next_offset = line_offsets[i + 1] if i + 1 < len(line_offsets) else len(section_text) + 1
            if offset <= match.start() < next_offset:
                line_index = i
                break
        matches.append({"match": match, "line_index": line_index})

    for i, item in enumerate(matches):
        idx = item["line_index"]
        previous_idx = matches[i - 1]["line_index"] if i > 0 else -1
        next_idx = matches[i + 1]["line_index"] if i + 1 < len(matches) else len(lines)

        start_line = max(previous_idx + 1, idx - 4, 0)
        end_line = min(len(lines), idx + 14)
        if next_idx < len(lines):
            end_line = min(end_line, max(idx + 1, next_idx - 2))

        block_lines = [line.strip() for line in lines[start_line:end_line] if line.strip()]
        item["block"] = "\n".join(block_lines)

    return matches


def _looks_like_work_block(block: str) -> bool:
    normalized = normalize_token(block)
    tokens = set(normalized.split())
    return bool(tokens & WORK_CUES)


def experience_match(resume_text: str, jd_text: str, jd_skills: list[str]) -> dict:
    requirement_details = extract_requirement_details(jd_text)
    requirement = requirement_details["years"]
    max_requirement = requirement_details.get("max_years")

    role_terms = _job_role_terms(jd_text)
    domain_terms = _jd_domain_terms(jd_text)
    jd_relevance_text = _jd_relevance_text(jd_text)

    experience_text, section_found = extract_experience_section(resume_text)
    date_items = _date_matches_with_blocks(experience_text)

    intervals_all = []
    intervals_relevant = []
    evidence = []
    detected_jobs = []

    normalized_jd_skills = {
        skill: normalize_token(skill)
        for skill in jd_skills
        if normalize_token(skill)
    }

    for item in date_items:
        match = item["match"]
        block = item["block"]

        try:
            start = _parse_date(match.group("start"), is_end=False)
            end = _parse_date(match.group("end"), is_end=True)
            if end < start:
                continue
        except Exception:
            continue

        work_like = section_found or _looks_like_work_block(block)
        if not work_like:
            continue

        intervals_all.append((start, end))

        low_block = normalize_token(block)
        block_tokens = set(re.findall(r"[a-z][a-z0-9+#./-]{1,}", low_block))

        skill_hits = [
            skill for skill, normalized in normalized_jd_skills.items()
            if normalized and normalized in low_block
        ]

        role_hits = sorted(role_terms & block_tokens)
        distinctive_role_hits = [
            term for term in role_hits if term not in GENERIC_ROLE_WORDS
        ]

        domain_hits = sorted(
            term for term in (domain_terms & block_tokens)
            if term not in RELEVANCE_STOPWORDS
        )

        similarity = _lexical_similarity(block, jd_relevance_text)

        # Generic relevance:
        # 1) explicit JD skill, OR
        # 2) distinctive target role, OR
        # 3) multiple role/domain terms, OR
        # 4) sufficient block-to-JD lexical similarity.
        relevant = bool(
            skill_hits
            or distinctive_role_hits
            or len(role_hits) >= 2
            or len(domain_hits) >= 2
            or similarity >= 0.055
        )

        duration_years = round(_months_between(start, end) / 12, 1)

        detected_jobs.append({
            "period": match.group(0).strip(),
            "duration_years": duration_years,
            "relevant": relevant,
            "matched_skills": skill_hits[:8],
            "matched_role_terms": role_hits[:8],
            "matched_domain_terms": domain_hits[:12],
            "jd_similarity": round(similarity * 100, 1),
            "block": block[:700],
        })

        if relevant:
            intervals_relevant.append((start, end))
            evidence.append(block[:420])

    total_months = _merge_intervals(intervals_all)
    relevant_months = _merge_intervals(intervals_relevant)

    total_years = round(total_months / 12, 1)
    relevant_years = round(relevant_months / 12, 1)

    if requirement is not None:
        if relevant_years > 0:
            # For "4 to 5 years", 4 is the minimum threshold.
            years_score = min(100.0, (relevant_years / requirement) * 100)
        elif total_years > 0:
            years_score = 35.0
        else:
            years_score = 20.0
    else:
        if relevant_years >= 3:
            years_score = 90.0
        elif relevant_years >= 1:
            years_score = 80.0
        elif relevant_years > 0:
            years_score = 65.0
        elif total_years > 0:
            years_score = 45.0
        else:
            years_score = 35.0

    domain_match = match_experience_domain_requirements(resume_text, jd_text)
    if domain_match["score"] is not None:
        # Explicit business-area/industry requirements are part of experience fitness.
        score = years_score * 0.75 + domain_match["score"] * 0.25
    else:
        score = years_score

    return {
        "score": round(score, 1),
        "years_score": round(years_score, 1),
        "required_years": requirement,
        "max_required_years": max_requirement,
        "requirement_text": requirement_details["text"],
        "requirement_source": requirement_details.get("source"),
        "total_years_detected": total_years,
        "relevant_years_detected": relevant_years,
        "experience_section_found": section_found,
        "detected_jobs": detected_jobs,
        "experience_domain_requirements": domain_match,
        "evidence": evidence[:5],
    }

