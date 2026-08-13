import re

from core.text_utils import detect_sections


def _safe_score(value, default: float = 0.0) -> float:
    """
    Convert a score into a safe float between 0 and 100.

    Handles:
    - None
    - int
    - float
    - numeric string
    """

    if value is None:
        return float(default)

    try:
        value = float(value)
    except (TypeError, ValueError):
        return float(default)

    return max(0.0, min(100.0, value))


def resume_quality_score(text: str) -> dict:
    """
    Calculate basic resume readability / ATS-friendly quality.

    This score measures resume structure only.
    It does NOT measure job compatibility.

    Checks:
    - Core sections
    - Email
    - Phone
    - Resume length
    - Bullet structure
    - Text cleanliness
    """

    score = 0.0
    checks = []

    sections = detect_sections(text)

    # =========================================================
    # 1. CORE SECTIONS
    # =========================================================

    essential_sections = [
        "skills",
        "experience",
        "education",
    ]

    section_hits = sum(
        1
        for section in essential_sections
        if sections.get(section)
    )

    section_points = (
        section_hits / len(essential_sections)
    ) * 35

    score += section_points

    checks.append(
        {
            "name": "Core sections",
            "passed": section_hits == len(essential_sections),
            "detail": (
                f"{section_hits}/{len(essential_sections)} "
                "essential sections detected"
            ),
        }
    )

    # =========================================================
    # 2. EMAIL
    # =========================================================

    has_email = bool(
        re.search(
            r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
            text,
            re.I,
        )
    )

    if has_email:
        score += 15

    checks.append(
        {
            "name": "Email",
            "passed": has_email,
            "detail": (
                "Email address detected"
                if has_email
                else "Email address not detected"
            ),
        }
    )

    # =========================================================
    # 3. PHONE NUMBER
    # =========================================================

    has_phone = bool(
        re.search(
            r"(?:\+?\d[\d\s().-]{7,}\d)",
            text,
        )
    )

    if has_phone:
        score += 10

    checks.append(
        {
            "name": "Phone",
            "passed": has_phone,
            "detail": (
                "Phone number detected"
                if has_phone
                else "Phone number not detected"
            ),
        }
    )

    # =========================================================
    # 4. RESUME LENGTH
    # =========================================================

    word_count = len(
        re.findall(
            r"\b\w+\b",
            text,
        )
    )

    good_length = 250 <= word_count <= 1400

    if good_length:
        score += 20

    elif 150 <= word_count <= 1800:
        score += 12

    else:
        score += 5

    checks.append(
        {
            "name": "Resume length",
            "passed": good_length,
            "detail": f"Approx. {word_count} words",
        }
    )

    # =========================================================
    # 5. BULLET STRUCTURE
    # =========================================================

    bullet_lines = len(
        re.findall(
            r"(?m)^\s*(?:[-•*]|\u2022)\s+",
            text,
        )
    )

    has_bullets = bullet_lines >= 3

    if has_bullets:
        score += 10
    else:
        score += 4

    checks.append(
        {
            "name": "Readable bullet structure",
            "passed": has_bullets,
            "detail": (
                f"{bullet_lines} bullet-like lines detected"
            ),
        }
    )

    # =========================================================
    # 6. TEXT CLEANLINESS
    # =========================================================

    suspicious_symbols = len(
        re.findall(
            r"[^\w\s.,:;@+/#()'’&%$!?–—-]",
            text,
        )
    )

    clean_ratio = (
        suspicious_symbols / max(len(text), 1)
    )

    clean = clean_ratio < 0.01

    if clean:
        score += 10
    else:
        score += 4

    checks.append(
        {
            "name": "Text cleanliness",
            "passed": clean,
            "detail": (
                "Text is parser-friendly"
                if clean
                else (
                    "Unusual symbols may reduce "
                    "parser readability"
                )
            ),
        }
    )

    return {
        "score": round(
            min(score, 100.0),
            1,
        ),
        "checks": checks,
        "sections": sections,
    }


def overall_score(
    field_score: float,
    skill_score: float,
    experience_score: float,
    education_score: float,
    semantic_score: float,
    keyword_score: float,
    quality_score: float,
) -> float:
    """
    Universal CV ↔ JD compatibility score.

    The SAME scoring logic is used for every field:
    - Software
    - EEE
    - Mechanical
    - Civil
    - Marketing
    - Finance
    - Data Science
    - Telecom
    - etc.

    Weighting:

    Field / Domain Match     30%
    Required Skills          25%
    Relevant Experience      20%
    Education                15%
    Semantic Similarity       5%
    Keyword Match             3%
    Resume Quality            2%

    Total                   100%

    Field/domain matching has the highest importance so that
    an unrelated CV cannot receive a high score simply because
    it has good formatting or generic professional language.
    """

    # =========================================================
    # MAKE ALL SCORES SAFE
    # =========================================================

    field_score = _safe_score(field_score)

    skill_score = _safe_score(skill_score)

    experience_score = _safe_score(experience_score)

    education_score = _safe_score(education_score)

    semantic_score = _safe_score(semantic_score)

    keyword_score = _safe_score(keyword_score)

    quality_score = _safe_score(quality_score)

    # =========================================================
    # UNIVERSAL WEIGHTED SCORE
    # =========================================================

    score = (
        field_score * 0.30
        + skill_score * 0.25
        + experience_score * 0.20
        + education_score * 0.15
        + semantic_score * 0.05
        + keyword_score * 0.03
        + quality_score * 0.02
    )

    # =========================================================
    # DOMAIN / FIELD GATE
    # =========================================================
    #
    # This prevents a CV from another profession from receiving
    # a misleadingly high compatibility score.
    #
    # Example:
    #
    # JD:
    # Electrical Engineer
    #
    # CV:
    # Frontend Developer
    #
    # Even if the CV is well-written, it should not receive
    # 55-60% just because of generic words or formatting.
    # =========================================================

    if field_score < 20:
        score = min(
            score,
            30.0,
        )

    elif field_score < 40:
        score = min(
            score,
            45.0,
        )

    elif field_score < 55:
        score = min(
            score,
            60.0,
        )

    # =========================================================
    # FINAL SAFE SCORE
    # =========================================================

    return round(
        max(
            0.0,
            min(
                100.0,
                score,
            ),
        ),
        1,
    )