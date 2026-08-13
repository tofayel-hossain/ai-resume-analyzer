import re

from core.text_utils import detect_sections


def resume_quality_score(text: str) -> dict:
    score = 0.0
    checks = []

    sections = detect_sections(text)

    essential = ["skills", "experience", "education"]
    section_hits = sum(1 for s in essential if sections.get(s))
    section_points = (section_hits / len(essential)) * 35
    score += section_points
    checks.append({
        "name": "Core sections",
        "passed": section_hits == len(essential),
        "detail": f"{section_hits}/{len(essential)} essential sections detected",
    })

    has_email = bool(re.search(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", text, re.I))
    score += 15 if has_email else 0
    checks.append({"name": "Email", "passed": has_email, "detail": "Email address detected" if has_email else "Email address not detected"})

    has_phone = bool(re.search(r"(?:\+?\d[\d\s().-]{7,}\d)", text))
    score += 10 if has_phone else 0
    checks.append({"name": "Phone", "passed": has_phone, "detail": "Phone number detected" if has_phone else "Phone number not detected"})

    word_count = len(re.findall(r"\b\w+\b", text))
    good_length = 250 <= word_count <= 1400
    if good_length:
        score += 20
    elif 150 <= word_count <= 1800:
        score += 12
    else:
        score += 5
    checks.append({
        "name": "Resume length",
        "passed": good_length,
        "detail": f"Approx. {word_count} words",
    })

    bullet_lines = len(re.findall(r"(?m)^\s*(?:[-•*]|[\u2022])\s+", text))
    has_bullets = bullet_lines >= 3
    score += 10 if has_bullets else 4
    checks.append({
        "name": "Readable bullet structure",
        "passed": has_bullets,
        "detail": f"{bullet_lines} bullet-like lines detected",
    })

    suspicious_symbols = len(re.findall(r"[^\w\s.,:;@+/#()'’&%$!?–—-]", text))
    clean_ratio = suspicious_symbols / max(len(text), 1)
    clean = clean_ratio < 0.01
    score += 10 if clean else 4
    checks.append({
        "name": "Text cleanliness",
        "passed": clean,
        "detail": "Text is parser-friendly" if clean else "Unusual symbols may reduce parser readability",
    })

    return {
        "score": round(min(score, 100.0), 1),
        "checks": checks,
        "sections": sections,
    }


def overall_score(
    skill_score: float,
    semantic_score: float,
    experience_score: float,
    keyword_score: float,
    quality_score: float,
) -> float:
    score = (
        skill_score * 0.30
        + semantic_score * 0.25
        + experience_score * 0.20
        + keyword_score * 0.15
        + quality_score * 0.10
    )
    return round(max(0.0, min(100.0, score)), 1)
