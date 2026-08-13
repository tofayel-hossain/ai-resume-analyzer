import math
import re
from dataclasses import dataclass

from core.text_utils import SECTION_ALIASES, normalize_token


JD_HEADINGS = {
    "requirements",
    "requirement",
    "education",
    "experience",
    "additional requirements",
    "responsibilities & context",
    "responsibilities and context",
    "responsibilities",
    "skills & expertise",
    "skills and expertise",
    "other relevant skills",
    "compensation & other benefits",
    "compensation and other benefits",
    "workplace",
    "employment status",
    "job location",
    "job responsibilities",
    "qualifications",
}


def _norm_heading(line: str) -> str:
    line = line.strip().lower().rstrip(":")
    line = line.replace("&", "and")
    line = re.sub(r"[^a-z0-9 +#./-]", " ", line)
    return re.sub(r"\s+", " ", line).strip()


NORMALIZED_JD_HEADINGS = {_norm_heading(x) for x in JD_HEADINGS}


def extract_section(text: str, headings: set[str], stop_headings: set[str] | None = None) -> tuple[str, bool]:
    """Extract a named section until the next recognized heading."""
    targets = {_norm_heading(x) for x in headings}
    stops = {_norm_heading(x) for x in (stop_headings or JD_HEADINGS)}
    lines = text.replace("\r\n", "\n").replace("\r", "\n").splitlines()

    start = None
    for i, line in enumerate(lines):
        if _norm_heading(line) in targets:
            start = i + 1
            break

    if start is None:
        return "", False

    end = len(lines)
    for i in range(start, len(lines)):
        h = _norm_heading(lines[i])
        if h in stops:
            end = i
            break

    return "\n".join(lines[start:end]).strip(), True


def extract_resume_section(text: str, section: str) -> tuple[str, bool]:
    aliases = SECTION_ALIASES.get(section, [])
    lines = text.replace("\r\n", "\n").replace("\r", "\n").splitlines()

    def is_heading(line: str, candidates: list[str]) -> bool:
        cleaned = _norm_heading(line)
        return any(cleaned == _norm_heading(x) for x in candidates)

    start = None
    for i, line in enumerate(lines):
        if is_heading(line, aliases):
            start = i + 1
            break
    if start is None:
        return "", False

    other = []
    for key, vals in SECTION_ALIASES.items():
        if key != section:
            other.extend(vals)

    end = len(lines)
    for i in range(start, len(lines)):
        if is_heading(lines[i], other):
            end = i
            break

    body = "\n".join(lines[start:end]).strip()
    return body, bool(body)


def build_jd_skill_text(jd_text: str) -> dict:
    """
    Build skill-requirement text from requirement-bearing JD sections.
    Nested headings such as "Responsibilities & Context" -> "Responsibilities:"
    are treated as the same logical section instead of stopping extraction.
    """
    relevant_headings = {
        "requirements", "requirement", "qualifications",
        "additional requirements",
        "responsibilities and context", "responsibilities", "job responsibilities",
        "skills and expertise", "other relevant skills",
    }
    hard_stops = {
        "compensation and other benefits",
        "workplace",
        "employment status",
        "job location",
    }

    label_map = {
        "requirements": "Requirements",
        "requirement": "Requirements",
        "qualifications": "Requirements",
        "additional requirements": "Additional Requirements",
        "responsibilities and context": "Responsibilities",
        "responsibilities": "Responsibilities",
        "job responsibilities": "Responsibilities",
        "skills and expertise": "Skills & Expertise",
        "other relevant skills": "Other Relevant Skills",
    }

    lines = jd_text.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    found = {label: "" for label in set(label_map.values())}
    buckets = {label: [] for label in found}
    current = None

    for line in lines:
        heading = _norm_heading(line)

        if heading in hard_stops:
            current = None
            continue

        if heading in relevant_headings:
            current = label_map[heading]
            continue

        # Education and Experience are handled by their dedicated matchers, not skill matching.
        if heading in {"education", "experience"}:
            current = None
            continue

        # Any other recognized JD heading ends the current capture.
        if heading in NORMALIZED_JD_HEADINGS and heading not in relevant_headings:
            current = None
            continue

        if current and line.strip():
            # Preferred/additional-advantage lines are reported separately and
            # must not reduce the core skill score.
            if re.search(
                r"\b(?:added\s+advantage|additional\s+advantage|preferred|preference|priority|will\s+get\s+preference)\b",
                line,
                flags=re.I,
            ):
                continue
            # Sensitive personal criteria are never used as core matching inputs.
            if any(pattern.search(line) for pattern in SENSITIVE_PATTERNS.values()):
                continue
            buckets[current].append(line.strip())

    parts = []
    for label, rows in buckets.items():
        body = "\n".join(rows).strip()
        found[label] = body
        if body:
            parts.append(body)

    # If the JD is unstructured, fall back to the whole text.
    requirement_text = "\n".join(parts).strip() if parts else jd_text
    return {"text": requirement_text, "sections": found}


DEGREE_ALIASES = {
    "PhD": ["phd", "ph.d", "doctor of philosophy"],
    "Master": ["master", "msc", "m.sc", "ms ", "m.s ", "mba", "m.eng", "meng"],
    "Bachelor": ["bachelor", "bsc", "b.sc", "b.sc.", "beng", "b.eng", "bachelor of science", "bachelor of engineering", "bsc engineer"],
    "Diploma": ["diploma", "diploma in engineering", "polytechnic"],
    "HSC": ["hsc", "higher secondary"],
    "SSC": ["ssc", "secondary school certificate"],
}

FIELD_ALIASES = {
    "Electrical & Electronic Engineering (EEE)": [
        "electrical and electronic engineering",
        "electrical & electronic engineering",
        "electrical and electronics engineering",
        "electrical & electronics engineering",
        "electrical electronic engineering",
        "eee",
    ],
    "Electronics & Communication Engineering (ECE)": [
        "electronics and communication engineering",
        "electronic and communication engineering",
        "electronics & communication engineering",
        "ece",
    ],
    "Mechanical Engineering": ["mechanical engineering", "mechanical", "me"],
    "Computer Science / CSE": [
        "computer science and engineering", "computer science", "cse", "computer engineering"
    ],
    "Civil Engineering": ["civil engineering", "civil"],
    "Telecommunication Engineering": [
        "telecommunication engineering", "telecommunications engineering", "telecom engineering"
    ],
}


def _contains_alias(text: str, alias: str) -> bool:
    norm = normalize_token(text)
    a = normalize_token(alias).strip()
    if not a:
        return False
    if len(a) <= 3:
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(a)}(?![a-z0-9])", norm))
    return a in norm


def _detect_aliases(text: str, mapping: dict[str, list[str]]) -> list[str]:
    found = []
    for canonical, aliases in mapping.items():
        if any(_contains_alias(text, alias) for alias in aliases):
            found.append(canonical)
    return found


def education_match(resume_text: str, jd_text: str) -> dict:
    jd_education, jd_found = extract_section(jd_text, {"education", "qualifications"})
    resume_education, resume_found = extract_resume_section(resume_text, "education")

    jd_scan = jd_education if jd_found else jd_text
    cv_scan = resume_education if resume_found else resume_text

    required_degrees = _detect_aliases(jd_scan, DEGREE_ALIASES)
    accepted_fields = _detect_aliases(jd_scan, FIELD_ALIASES)
    cv_degrees = _detect_aliases(cv_scan, DEGREE_ALIASES)
    cv_fields = _detect_aliases(cv_scan, FIELD_ALIASES)

    degree_match = bool(set(required_degrees) & set(cv_degrees)) if required_degrees else None
    field_match = bool(set(accepted_fields) & set(cv_fields)) if accepted_fields else None

    requires_ugc = bool(re.search(r"\bUGC\s+approved\b|\bapproved\s+university\b", jd_scan, flags=re.I))
    institution_verified = None
    if requires_ugc:
        # Offline project cannot safely verify an institution against the live UGC list.
        institution_verified = "Needs external verification"

    components = []
    if degree_match is not None:
        components.append(100.0 if degree_match else 0.0)
    if field_match is not None:
        components.append(100.0 if field_match else 0.0)

    score = round(sum(components) / len(components), 1) if components else 70.0

    core_fulfilled = all(
        x is not False for x in (degree_match, field_match)
    ) and bool(components)

    if not components:
        status = "No explicit education requirement detected"
    elif core_fulfilled and requires_ugc:
        status = "Core education matched; institution approval needs verification"
    elif core_fulfilled:
        status = "Education requirement fulfilled"
    else:
        status = "Education requirement not fully fulfilled"

    return {
        "score": score,
        "status": status,
        "jd_section_found": jd_found,
        "resume_section_found": resume_found,
        "jd_text": jd_education if jd_found else None,
        "resume_text": resume_education if resume_found else None,
        "required_degrees": required_degrees,
        "accepted_fields": accepted_fields,
        "cv_degrees": cv_degrees,
        "cv_fields": cv_fields,
        "degree_match": degree_match,
        "field_match": field_match,
        "requires_ugc_approved": requires_ugc,
        "institution_verification": institution_verified,
    }


# Coordinates are intentionally coarse city/neighborhood centroids, not personal addresses.
LOCATION_COORDS = {
    "mohakhali": (23.7785, 90.3977, "Dhaka"),
    "banani": (23.7937, 90.4066, "Dhaka"),
    "gulshan": (23.7925, 90.4078, "Dhaka"),
    "tejgaon": (23.7630, 90.3937, "Dhaka"),
    "farmgate": (23.7574, 90.3895, "Dhaka"),
    "mirpur": (23.8223, 90.3654, "Dhaka"),
    "uttara": (23.8759, 90.3795, "Dhaka"),
    "dhanmondi": (23.7461, 90.3742, "Dhaka"),
    "mohammadpur": (23.7658, 90.3584, "Dhaka"),
    "badda": (23.7805, 90.4264, "Dhaka"),
    "bashundhara": (23.8151, 90.4255, "Dhaka"),
    "motijheel": (23.7334, 90.4179, "Dhaka"),
    "jatrabari": (23.7104, 90.4348, "Dhaka"),
    "dhaka": (23.8103, 90.4125, "Dhaka"),
    "gazipur": (23.9999, 90.4203, "Gazipur"),
    "narayanganj": (23.6238, 90.5000, "Narayanganj"),
    "savar": (23.8583, 90.2667, "Dhaka"),
    "chattogram": (22.3569, 91.7832, "Chattogram"),
    "chittagong": (22.3569, 91.7832, "Chattogram"),
    "sylhet": (24.8949, 91.8687, "Sylhet"),
    "khulna": (22.8456, 89.5403, "Khulna"),
    "rajshahi": (24.3745, 88.6042, "Rajshahi"),
    "barishal": (22.7010, 90.3535, "Barishal"),
    "barisal": (22.7010, 90.3535, "Barishal"),
    "rangpur": (25.7439, 89.2752, "Rangpur"),
    "mymensingh": (24.7471, 90.4203, "Mymensingh"),
    "cumilla": (23.4607, 91.1809, "Cumilla"),
    "comilla": (23.4607, 91.1809, "Cumilla"),
}


def _detect_location_candidates(text: str, first_lines_only: bool = False) -> list[str]:
    scan = "\n".join(text.splitlines()[:60]) if first_lines_only else text
    low = normalize_token(scan)
    found = []
    # Prefer specific areas over the generic city label.
    for name in sorted(LOCATION_COORDS, key=len, reverse=True):
        if re.search(rf"(?<![a-z0-9]){re.escape(name)}(?![a-z0-9])", low):
            found.append(name)
    return found


def _haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    return 6371.0 * 2 * math.asin(math.sqrt(h))


def location_match(resume_text: str, jd_text: str) -> dict:
    jd_location, jd_found = extract_section(jd_text, {"job location"})
    jd_candidates = _detect_location_candidates(jd_location if jd_found else jd_text)
    cv_candidates = _detect_location_candidates(resume_text, first_lines_only=True)

    # Most-specific detected term; generic Dhaka comes after areas because of sorting.
    jd_name = jd_candidates[0] if jd_candidates else None
    cv_name = cv_candidates[0] if cv_candidates else None

    result = {
        "jd_location_text": jd_location if jd_found else None,
        "jd_location": jd_name,
        "cv_location": cv_name,
        "distance_km": None,
        "status": "Unknown",
        "note": "Location is shown as logistical information and is not included in the compatibility score.",
    }

    if not jd_name:
        result["status"] = "Job location not detected"
        return result
    if not cv_name:
        result["status"] = "CV location not detected"
        return result

    jd_lat, jd_lon, jd_city = LOCATION_COORDS[jd_name]
    cv_lat, cv_lon, cv_city = LOCATION_COORDS[cv_name]
    distance = round(_haversine_km((jd_lat, jd_lon), (cv_lat, cv_lon)), 1)
    result["distance_km"] = distance

    if jd_name == cv_name:
        status = "Same area"
    elif jd_city == cv_city and distance <= 15:
        status = "Nearby"
    elif jd_city == cv_city:
        status = "Same city"
    elif distance <= 35:
        status = "Nearby city/area"
    else:
        status = "Different location"

    result["status"] = status
    return result


EXPERIENCE_DOMAIN_ALIASES = {
    "Group of Companies": ["group of companies", "group company", "conglomerate"],
    "Telecommunication": ["telecommunication", "telecommunications", "telecom"],
    "Data Center": ["data center", "datacenter", "data centre"],
    "Manufacturing": ["manufacturing", "factory", "production"],
    "Banking": ["banking", "bank"],
    "FMCG": ["fmcg", "fast moving consumer goods"],
    "IT / Software": ["software company", "software industry", "information technology", "it company"],
}


def extract_experience_domain_requirements(jd_text: str) -> list[str]:
    """
    Extract explicit industry/business-area experience requirements.
    Example:
      The applicants should have experience in the following business area(s):
      Group of Companies, Telecommunication
    """
    found = []
    for raw_line in jd_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        m = re.search(
            r"(?:business\s+area\s*\(?s?\)?|industry(?:\s+area)?)\s*:\s*(.+)$",
            line,
            flags=re.I,
        )
        if not m:
            continue

        tail = m.group(1)
        for canonical, aliases in EXPERIENCE_DOMAIN_ALIASES.items():
            if any(_contains_alias(tail, alias) for alias in aliases):
                found.append(canonical)

        # Preserve unknown comma-separated domains for transparent display.
        if not found:
            for part in re.split(r"\s*,\s*|\s+or\s+", tail):
                part = part.strip(" .;")
                if part:
                    found.append(part)

    return list(dict.fromkeys(found))


def match_experience_domain_requirements(resume_text: str, jd_text: str) -> dict:
    required = extract_experience_domain_requirements(jd_text)
    low_resume = normalize_token(resume_text)

    matched = []
    missing = []
    evidence = {}

    for requirement in required:
        aliases = EXPERIENCE_DOMAIN_ALIASES.get(requirement, [requirement])
        hits = [
            alias for alias in aliases
            if _contains_alias(low_resume, alias)
        ]
        if hits:
            matched.append(requirement)
            evidence[requirement] = hits[:3]
        else:
            missing.append(requirement)

    score = round((len(matched) / len(required)) * 100, 1) if required else None
    return {
        "required": required,
        "matched": matched,
        "missing": missing,
        "score": score,
        "evidence": evidence,
    }


SENSITIVE_PATTERNS = {
    "religion": re.compile(r"\b(?:religion|religious|muslim|non[- ]?muslim|hindu|christian|buddhist)\b", re.I),
    "age": re.compile(r"\bage\b|(?:at\s+least|maximum|minimum)\s+\d+\s+years\s+old", re.I),
    "gender": re.compile(r"\b(?:gender|male|female|man|woman|men|women)\b", re.I),
    "marital status": re.compile(r"\b(?:marital|married|unmarried|single)\b", re.I),
    "disability": re.compile(r"\b(?:disability|disabled)\b", re.I),
    "ethnicity/nationality": re.compile(r"\b(?:ethnicity|ethnic|nationality|race)\b", re.I),
}

ADVANTAGE_CUES = re.compile(
    r"\b(?:added\s+advantage|additional\s+advantage|an?\s+advantage|preferred|preference|priority|"
    r"will\s+get\s+preference|will\s+get\s+priority|considered\s+as\s+added\s+advantage|"
    r"will\s+be\s+an?\s+added\s+advantage)\b",
    re.I,
)

GENERIC_ADVANTAGE_WORDS = {
    "added", "additional", "advantage", "preferred", "preference", "priority",
    "considered", "candidate", "candidates", "will", "get", "be", "an", "a",
    "as", "the", "and", "or", "in", "on", "of", "for", "with", "working",
    "experience", "related", "any", "other", "certification", "certifications",
}


def _split_requirement_lines(jd_text: str) -> list[str]:
    # JD data is often line-oriented. Also split long lines by sentence punctuation.
    out = []
    for line in jd_text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = re.split(r"(?<=[.!?])\s+", line)
        out.extend(p.strip() for p in parts if p.strip())
    return out


def _sensitive_category(text: str) -> str | None:
    for category, pattern in SENSITIVE_PATTERNS.items():
        if pattern.search(text):
            return category
    return None


def _important_terms(text: str) -> list[str]:
    norm = normalize_token(text)
    tokens = re.findall(r"[a-z][a-z0-9+#./-]{2,}", norm)
    return [
        t for t in tokens
        if t not in GENERIC_ADVANTAGE_WORDS and len(t) >= 3
    ]


def _priority_match(item: str, resume_text: str) -> tuple[bool, list[str]]:
    low_resume = normalize_token(resume_text)
    item_low = normalize_token(item)

    synonym_groups = {
        "Data Center": ["data center", "datacenter", "data centre"],
        "CDCP": ["cdcp", "certified data centre professional", "certified data center professional"],
        "CDFOM": ["cdfom", "certified data centre facilities operations manager", "certified data center facilities operations manager"],
        "Telecommunication": ["telecommunication", "telecommunications", "telecom"],
        "Group of Companies": ["group of companies", "group company", "conglomerate"],
    }

    # Certification preference must be evidenced by the named certification itself.
    if "certification" in item_low or "certificate" in item_low:
        credential_hits = []
        for label in ("CDCP", "CDFOM"):
            aliases = synonym_groups[label]
            item_has = any(normalize_token(a) in item_low for a in aliases)
            resume_has = any(normalize_token(a) in low_resume for a in aliases)
            if item_has and resume_has:
                credential_hits.append(label)
        return (bool(credential_hits), credential_hits)

    evidence = []
    for label, aliases in synonym_groups.items():
        item_has = any(normalize_token(a) in item_low for a in aliases)
        resume_has = any(normalize_token(a) in low_resume for a in aliases)
        if item_has and resume_has:
            evidence.append(label)

    terms = _important_terms(item)
    term_hits = [
        t for t in terms
        if re.search(rf"(?<![a-z0-9]){re.escape(t)}(?![a-z0-9])", low_resume)
    ]
    evidence.extend(term_hits[:6])

    evidence = list(dict.fromkeys(evidence))
    return (len(evidence) >= 1), evidence


def priority_requirements_match(resume_text: str, jd_text: str) -> dict:
    matched = []
    unmatched = []
    excluded = []

    for line in _split_requirement_lines(jd_text):
        if not ADVANTAGE_CUES.search(line):
            continue

        sensitive = _sensitive_category(line)
        if sensitive:
            excluded.append({
                "text": line,
                "reason": (
                    f"Sensitive personal characteristic ({sensitive}); excluded from automated candidate matching/scoring."
                ),
            })
            continue

        is_match, evidence = _priority_match(line, resume_text)
        row = {"text": line, "matched": is_match, "evidence": evidence}
        (matched if is_match else unmatched).append(row)

    # Also flag standalone sensitive additional requirements such as "Age at least 27 years"
    # even when they are not written as an advantage.
    for line in _split_requirement_lines(jd_text):
        sensitive = _sensitive_category(line)
        if sensitive and not any(x["text"] == line for x in excluded):
            if re.search(r"\b(?:requirement|age|candidate|applicant|must|should)\b", line, re.I):
                excluded.append({
                    "text": line,
                    "reason": (
                        f"Sensitive personal characteristic ({sensitive}); excluded from automated candidate matching/scoring."
                    ),
                })

    return {
        "matched": matched,
        "unmatched": unmatched,
        "excluded_sensitive": excluded,
        "total_non_sensitive": len(matched) + len(unmatched),
    }


def build_requirement_comparison(resume_text: str, jd_text: str) -> dict:
    return {
        "skill_requirements": build_jd_skill_text(jd_text),
        "education": education_match(resume_text, jd_text),
        "location": location_match(resume_text, jd_text),
        "priority": priority_requirements_match(resume_text, jd_text),
    }
