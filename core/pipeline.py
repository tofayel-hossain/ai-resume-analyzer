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
    Try to detect a real job title without accidentally using
    Education / Requirement text as the title.
    """

    lines = [
        line.strip()
        for line in jd_text.splitlines()
        if line.strip()
    ]

    # ---------------------------------------------------------
    # 1. Prefer explicit Job Title / Position / Role labels
    # ---------------------------------------------------------

    explicit_patterns = [
        r"^job\s*title\s*:\s*(.+)$",
        r"^position\s*:\s*(.+)$",
        r"^role\s*:\s*(.+)$",
    ]

    for line in lines[:30]:
        for pattern in explicit_patterns:
            match = re.match(
                pattern,
                line,
                flags=re.I,
            )

            if match:
                title = match.group(1).strip()

                if title:
                    return title[:120]

    # ---------------------------------------------------------
    # 2. Search likely role-title lines
    # ---------------------------------------------------------

    role_terms = (
        "engineer",
        "developer",
        "analyst",
        "scientist",
        "manager",
        "designer",
        "architect",
        "specialist",
        "administrator",
        "intern",
        "consultant",
        "executive",
        "officer",
        "technician",
        "coordinator",
        "supervisor",
        "accountant",
        "auditor",
        "marketer",
        "sales",
        "recruiter",
    )

    # Lines containing these are usually requirements,
    # not actual job titles.
    reject_terms = (
        "bachelor",
        "bsc",
        "b.sc",
        "master",
        "msc",
        "degree",
        "diploma",
        "education",
        "requirement",
        "requirements",
        "preferred",
        "experience",
        "responsibilities",
        "skills",
        "qualification",
        "university",
    )

    for line in lines[:25]:
        low = line.lower()

        if len(line) > 100:
            continue

        if any(term in low for term in reject_terms):
            continue

        if any(
            re.search(
                rf"\b{re.escape(term)}\b",
                low,
            )
            for term in role_terms
        ):
            return line[:120]

    return "Target Role"


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
    update(15, "Extracting resume...")
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
    update(35, "Processing information...")
    requirements = build_requirement_comparison(
        resume_text,
        jd_text,
    )

    # =========================================================
    # 3. SKILL MATCH
    # =========================================================
    update(55, "Matching CV with Job Description...")
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
    update(75, "Calculating compatibility score...")
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
    update(90, "Preparing output...")
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