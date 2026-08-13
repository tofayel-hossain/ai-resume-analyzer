import re

from core.ats import overall_score, resume_quality_score
from core.experience import experience_match
from core.file_parser import extract_resume_text
from core.generation import (
    build_explanation,
    build_interview_questions,
    build_suggestions,
)
from core.keyword_analyzer import keyword_analysis
from core.requirements_matcher import build_requirement_comparison
from core.semantic import semantic_similarity
from core.skills import match_skills
from core.text_utils import clean_text


def _safe_score(value, default: float = 0.0) -> float:
    """
    Convert a score to a safe float between 0 and 100.
    """

    if value is None:
        return float(default)

    try:
        value = float(value)
    except (TypeError, ValueError):
        return float(default)

    return max(0.0, min(100.0, value))


def extract_job_title(jd_text: str) -> str:
    """
    Extract the most likely job title from a Job Description.

    Priority:
    1. Explicit labels: Job Title, Position, Role, Vacancy
    2. Short title-like lines containing profession terms
    3. Avoid education, requirement, company, location and section headings
    """

    lines = [
        re.sub(r"\s+", " ", line).strip(" :-•\t")
        for line in jd_text.splitlines()
        if line.strip()
    ]

    if not lines:
        return ""

    # =========================================================
    # 1. EXPLICIT JOB TITLE LABELS
    # =========================================================

    explicit_patterns = [
        r"^job\s*title\s*[:\-]\s*(.+)$",
        r"^position\s*[:\-]\s*(.+)$",
        r"^position\s*title\s*[:\-]\s*(.+)$",
        r"^role\s*[:\-]\s*(.+)$",
        r"^job\s*role\s*[:\-]\s*(.+)$",
        r"^vacancy\s*for\s*[:\-]?\s*(.+)$",
        r"^hiring\s*for\s*[:\-]?\s*(.+)$",
        r"^we\s+are\s+hiring\s*[:\-]?\s*(.+)$",
    ]

    for line in lines[:40]:
        for pattern in explicit_patterns:
            match = re.match(
                pattern,
                line,
                flags=re.I,
            )

            if match:
                title = match.group(1).strip()

                if _valid_job_title(title):
                    return title[:120]

    # =========================================================
    # 2. COMMON ROLE WORDS
    # =========================================================

    role_terms = (
        # Engineering / Technology
        "engineer",
        "developer",
        "programmer",
        "architect",
        "administrator",
        "technician",
        "operator",

        # Data / Research
        "analyst",
        "scientist",
        "researcher",
        "statistician",

        # Management / Leadership
        "manager",
        "director",
        "head",
        "supervisor",
        "coordinator",
        "lead",

        # Business / Corporate
        "executive",
        "officer",
        "specialist",
        "consultant",
        "advisor",
        "associate",
        "assistant",
        "representative",

        # Finance / Accounting
        "accountant",
        "auditor",
        "banker",
        "economist",
        "treasurer",

        # HR
        "recruiter",
        "recruitment",
        "human resources",

        # Sales / Marketing
        "marketer",
        "sales",
        "marketing",
        "merchandiser",
        "brand manager",

        # Design / Creative
        "designer",
        "writer",
        "copywriter",
        "editor",
        "photographer",
        "animator",

        # Education
        "teacher",
        "lecturer",
        "professor",
        "instructor",
        "trainer",

        # Medical / Healthcare
        "doctor",
        "physician",
        "nurse",
        "pharmacist",
        "therapist",
        "surgeon",
        "dentist",

        # Legal
        "lawyer",
        "attorney",
        "advocate",
        "paralegal",

        # Entry level
        "intern",
        "trainee",
    )

    # =========================================================
    # 3. LINES THAT SHOULD NOT BECOME JOB TITLES
    # =========================================================

    reject_terms = (
        "bachelor",
        "b.sc",
        "bsc",
        "master",
        "m.sc",
        "msc",
        "degree",
        "diploma",
        "education",
        "qualification",
        "academic",
        "university",
        "college",

        "experience required",
        "years of experience",
        "minimum experience",

        "job description",
        "job responsibilities",
        "responsibilities",
        "requirements",
        "additional requirements",
        "preferred qualifications",
        "skills",
        "skills required",
        "technical skills",

        "salary",
        "compensation",
        "benefits",
        "location",
        "workplace",
        "employment status",
        "vacancy",
        "application deadline",

        "about us",
        "about company",
        "company overview",
        "company name",
    )

    # =========================================================
    # 4. SCORE TITLE-LIKE LINES
    # =========================================================

    candidates = []

    for index, line in enumerate(lines[:40]):
        low = line.lower().strip()

        if not _valid_job_title(line):
            continue

        if any(term in low for term in reject_terms):
            continue

        score = 0

        # Short lines are more likely to be titles.
        word_count = len(line.split())

        if 2 <= word_count <= 6:
            score += 5
        elif word_count <= 10:
            score += 2
        else:
            score -= 4

        # Earlier lines are more likely to contain title.
        if index <= 3:
            score += 5
        elif index <= 8:
            score += 3
        elif index <= 15:
            score += 1

        # Strong role-word match.
        matched_roles = [
            term
            for term in role_terms
            if re.search(
                rf"(?<!\w){re.escape(term)}(?!\w)",
                low,
                flags=re.I,
            )
        ]

        if not matched_roles:
            continue

        score += 8

        # Seniority words make title more likely.
        if re.search(
            r"\b("
            r"senior|sr\.?|junior|jr\.?|lead|principal|"
            r"associate|assistant|deputy|chief|head|"
            r"entry[- ]level"
            r")\b",
            low,
            flags=re.I,
        ):
            score += 3

        # Sentences are less likely to be titles.
        if line.endswith((".", "!", "?")):
            score -= 4

        # Too many commas usually indicates requirement text.
        if line.count(",") >= 2:
            score -= 3

        candidates.append(
            (
                score,
                index,
                line,
            )
        )

    # =========================================================
    # 5. RETURN BEST CANDIDATE
    # =========================================================

    if candidates:
        candidates.sort(
            key=lambda item: (
                -item[0],
                item[1],
            )
        )

        best_score, _, best_title = candidates[0]

        # Prevent weak/random guesses.
        if best_score >= 8:
            return best_title[:120]

    return "Job Role Not Detected"


def _valid_job_title(text: str) -> bool:
    """
    Reject obvious non-title strings.
    """

    text = text.strip()

    if not text:
        return False

    if len(text) > 120:
        return False

    words = text.split()

    if len(words) > 12:
        return False

    low = text.lower()

    # URLs / email-like content
    if "http://" in low or "https://" in low:
        return False

    if "@" in text:
        return False

    # Mostly numerical lines
    if re.fullmatch(
        r"[\d\s./\-–]+",
        text,
    ):
        return False

    return True

def calculate_field_match(
    skills: dict,
    experience: dict,
    education: dict,
) -> dict:
    """
    Calculate one UNIVERSAL Field / Domain Match score.

    The same logic is used for all professions:
    Software, EEE, Mechanical, Civil, Finance,
    Marketing, Telecom, Data Center, etc.

    Field match is based on available evidence:

    1. JD experience/responsibility vs CV work evidence  -> 40%
    2. Required JD skills vs CV skills                   -> 30%
    3. Explicit business/industry area match             -> 15%
    4. Explicit education field match                    -> 15%

    If one component is not explicitly available in the JD,
    the remaining available components are automatically
    re-normalized instead of treating the missing component as zero.
    """

    components = []

    # =========================================================
    # 1. EXPERIENCE / RESPONSIBILITY DOMAIN MATCH
    # =========================================================

    responsibility_score = experience.get(
        "responsibility_match_score"
    )

    if responsibility_score is not None:
        components.append(
            {
                "name": "Experience responsibilities",
                "score": _safe_score(
                    responsibility_score
                ),
                "weight": 0.40,
            }
        )

    # =========================================================
    # 2. REQUIRED SKILL MATCH
    # =========================================================

    skill_score = skills.get("score")

    if skill_score is not None:
        components.append(
            {
                "name": "Required skills",
                "score": _safe_score(
                    skill_score
                ),
                "weight": 0.30,
            }
        )

    # =========================================================
    # 3. BUSINESS / INDUSTRY DOMAIN MATCH
    # =========================================================

    domain_data = experience.get(
        "experience_domain_requirements",
        {}
    ) or {}

    domain_score = domain_data.get("score")

    # Only include this component if the JD explicitly
    # contains business/industry-area requirements.
    if domain_score is not None:
        components.append(
            {
                "name": "Business / industry area",
                "score": _safe_score(
                    domain_score
                ),
                "weight": 0.15,
            }
        )

    # =========================================================
    # 4. EDUCATION FIELD MATCH
    # =========================================================

    accepted_fields = education.get(
        "accepted_fields",
        []
    ) or []

    education_field_match = education.get(
        "field_match"
    )

    # Education field affects DOMAIN match only when
    # the JD explicitly names acceptable study fields.
    if accepted_fields:

        if education_field_match is True:
            education_field_score = 100.0

        elif education_field_match is False:
            education_field_score = 0.0

        else:
            # Requirement exists but parser could not confirm.
            education_field_score = 50.0

        components.append(
            {
                "name": "Education field",
                "score": education_field_score,
                "weight": 0.15,
            }
        )

    # =========================================================
    # FALLBACK
    # =========================================================

    if not components:
        return {
            "score": 0.0,
            "status": "Field match could not be determined",
            "components": [],
        }

    # =========================================================
    # DYNAMIC WEIGHTED AVERAGE
    # =========================================================

    total_weight = sum(
        item["weight"]
        for item in components
    )

    weighted_total = sum(
        item["score"] * item["weight"]
        for item in components
    )

    if total_weight <= 0:
        field_score = 0.0
    else:
        field_score = (
            weighted_total / total_weight
        )

    field_score = round(
        max(
            0.0,
            min(
                100.0,
                field_score,
            ),
        ),
        1,
    )

    # =========================================================
    # SIMPLE STATUS
    # =========================================================

    if field_score >= 80:
        status = "Strong same-field match"

    elif field_score >= 65:
        status = "Good field match"

    elif field_score >= 50:
        status = "Moderate field match"

    elif field_score >= 35:
        status = "Weak field match"

    else:
        status = "Low / different-field match"

    return {
        "score": field_score,
        "status": status,
        "components": components,
    }


def analyze(
    file_bytes: bytes,
    filename: str,
    jd_text: str,
    progress_callback=None,
):
    """
    Run the complete Resume ↔ Job Description analysis.
    """

    def update(percent, message):
        if progress_callback:
            progress_callback(percent, message)

    # =========================================================
    # 1. RESUME + JD TEXT
    # =========================================================
    update(5, "Extracting resume...")
    resume_raw = extract_resume_text(
        file_bytes,
        filename,
    )

    resume_text = clean_text(
        resume_raw
    )

    jd_text = clean_text(
        jd_text
    )

    # =========================================================
    # 2. STRUCTURED JD REQUIREMENTS
    # =========================================================
    update(25, "Processing information...")
    requirements = build_requirement_comparison(
        resume_text,
        jd_text,
    )

    # =========================================================
    # 3. SKILL MATCH
    # =========================================================
    update(45, "Matching CV with Job Description...")
    # Only use requirement-bearing JD sections.
    # Benefits / location / sensitive criteria should not
    # reduce the actual required-skill score.
    skill_text = requirements[
        "skill_requirements"
    ]["text"]

    skills = match_skills(
        resume_text,
        skill_text,
    )

    # =========================================================
    # 4. KEYWORD ANALYSIS
    # =========================================================

    keywords = keyword_analysis(
        resume_text,
        jd_text,
    )

    # =========================================================
    # 5. SEMANTIC SIMILARITY
    # =========================================================

    semantic = semantic_similarity(
        resume_text,
        jd_text,
    )

    # =========================================================
    # 6. EXPERIENCE MATCH
    # =========================================================
    
    experience = experience_match(
        resume_text,
        jd_text,
        skills.get(
            "jd_skills",
            [],
        ),
    )

    # =========================================================
    # 7. EDUCATION / LOCATION / ADVANTAGES
    # =========================================================

    education = requirements.get(
        "education",
        {},
    )

    location = requirements.get(
        "location",
        {},
    )

    priority = requirements.get(
        "priority",
        {},
    )

    # =========================================================
    # 8. RESUME QUALITY
    # =========================================================

    quality = resume_quality_score(
        resume_text
    )

    # =========================================================
    # 9. SAFE SKILL SCORE
    # =========================================================
    update(65, "Calculating compatibility score...")
    skill_score = skills.get(
        "score"
    )

    # If no catalogued JD skills were extracted,
    # use keyword coverage only as a technical fallback.
    if skill_score is None:

        skill_score = _safe_score(
            keywords.get(
                "coverage_score",
                0.0,
            )
        )

        skills["score"] = skill_score
        skills[
            "score_fallback"
        ] = "keyword coverage"

    else:
        skill_score = _safe_score(
            skill_score
        )

    # =========================================================
    # 10. FIELD / DOMAIN MATCH
    # =========================================================

    field = calculate_field_match(
        skills=skills,
        experience=experience,
        education=education,
    )

    field_score = field[
        "score"
    ]

    # =========================================================
    # 11. SAFE COMPONENT SCORES
    # =========================================================
    semantic_score = _safe_score(
        semantic.get(
            "score",
            0.0,
        )
    )

    experience_score = _safe_score(
        experience.get(
            "score",
            0.0,
        )
    )

    education_score = _safe_score(
        education.get(
            "score",
            0.0,
        )
    )

    keyword_score = _safe_score(
        keywords.get(
            "coverage_score",
            0.0,
        )
    )

    quality_score = _safe_score(
        quality.get(
            "score",
            0.0,
        )
    )

    # =========================================================
    # 12. UNIVERSAL FINAL SCORE
    # =========================================================
    #
    # Your core/ats.py should use:
    #
    # Field / Domain     30%
    # Skills             25%
    # Experience         20%
    # Education          15%
    # Semantic            5%
    # Keywords             3%
    # Resume Quality       2%
    #
    # SAME logic for every profession.
    # =========================================================

    final = overall_score(
        field_score=field_score,
        skill_score=skill_score,
        experience_score=experience_score,
        education_score=education_score,
        semantic_score=semantic_score,
        keyword_score=keyword_score,
        quality_score=quality_score,
    )

    # =========================================================
    # 13. RESULT OBJECT
    # =========================================================
    update(85, "Preparing output...")
    result = {
        "job_title": extract_job_title(
            jd_text
        ),

        "resume_filename": filename,

        "resume_text": resume_text,

        "job_description": jd_text,

        "requirements": requirements,

        "field": field,

        "skills": skills,

        "keywords": keywords,

        "semantic": semantic,

        "experience": experience,

        "education": education,

        "location": location,

        # Keep the existing key for compatibility
        # with your current UI.
        "priority": priority,

        # Also expose a clearer alias if you later
        # want to use result["advantages"].
        "advantages": priority,

        "quality": quality,

        "scores": {
            "overall": final,
            "field": field_score,
            "skills": round(
                skill_score,
                1,
            ),
            "semantic": semantic_score,
            "experience": experience_score,
            "education": education_score,
            "keywords": keyword_score,
            "resume_quality": quality_score,
        },
    }

    # =========================================================
    # 14. EXPLANATION / SUGGESTIONS / INTERVIEW QUESTIONS
    # =========================================================

    result["explanation"] = build_explanation(
        result
    )

    result["suggestions"] = build_suggestions(
        result
    )

    result[
        "interview_questions"
    ] = build_interview_questions(
        result,
        resume_text,
    )
    update(100, "✓ Analysis ready")
    return result