from core.text_utils import find_evidence


def build_explanation(result: dict) -> dict:
    positive = []
    deductions = []
    notes = []

    matched = result["skills"]["matched"]
    missing = result["skills"]["missing"]
    exp = result["experience"]
    edu = result["education"]
    sem = result["semantic"]["score"]
    keyword = result["keywords"]["coverage_score"]
    quality = result["quality"]["score"]
    priority = result.get("priority", {})

    if matched:
        positive.append(f"{len(matched)} requirement skill(s) matched: {', '.join(matched[:8])}.")
    if edu["status"].startswith("Education requirement fulfilled") or edu["status"].startswith("Core education matched"):
        positive.append(edu["status"] + ".")
    if sem >= 75:
        positive.append(f"Strong semantic alignment between CV and JD ({sem:.0f}%).")
    elif sem >= 60:
        positive.append(f"Moderate semantic alignment between CV and JD ({sem:.0f}%).")
    if keyword >= 70:
        positive.append(f"Good JD keyword coverage ({keyword:.0f}%).")
    if quality >= 75:
        positive.append(f"Resume structure/readability score is strong ({quality:.0f}%).")
    if priority.get("matched"):
        positive.append(
            f"{len(priority['matched'])} non-sensitive preferred/additional-advantage item(s) were evidenced in the CV."
        )

    if missing:
        deductions.append(f"Required/preferred JD skills not found in the CV: {', '.join(missing[:8])}.")
    if exp["required_years"] is not None and exp["relevant_years_detected"] < exp["required_years"]:
        deductions.append(
            f"JD asks for at least {exp['required_years']:g} years, while the parser detected "
            f"about {exp['relevant_years_detected']:g} relevant years."
        )
    exp_domains = exp.get("experience_domain_requirements", {})
    if exp_domains.get("missing"):
        deductions.append(
            "Required experience business area(s) not evidenced in the CV: "
            + ", ".join(exp_domains["missing"]) + "."
        )
    if edu["degree_match"] is False or edu["field_match"] is False:
        deductions.append("CV education does not fully match the JD's detected degree/field requirement.")
    if keyword < 60:
        deductions.append(f"JD keyword coverage is relatively low ({keyword:.0f}%).")
    if sem < 60:
        deductions.append(f"CV↔JD semantic similarity is relatively low ({sem:.0f}%).")
    if quality < 70:
        failed = [c["name"] for c in result["quality"]["checks"] if not c["passed"]]
        if failed:
            deductions.append("Resume-format checks needing attention: " + ", ".join(failed[:4]) + ".")

    loc = result.get("location", {})
    if loc:
        notes.append(
            f"Location alignment: {loc.get('status', 'Unknown')}. "
            "Location is reported separately and is not part of the compatibility score."
        )
    if edu.get("requires_ugc_approved"):
        notes.append("JD mentions UGC/approved institution; this offline version does not verify live institutional approval.")
    if priority.get("excluded_sensitive"):
        notes.append(
            f"{len(priority['excluded_sensitive'])} sensitive personal criterion/criteria in the JD were excluded from automated matching and scoring."
        )

    if not positive:
        positive.append("The score is based on measurable requirement matches detected from the CV and JD.")
    if not deductions:
        deductions.append("No major rule-based core requirement gap was detected by this version.")

    return {
        "positive": positive,
        "deductions": deductions,
        "notes": notes,
        "note": (
            "This is an estimated compatibility score from transparent rules and NLP. "
            "It is not the proprietary score of any commercial ATS."
        ),
    }


def build_suggestions(result: dict) -> list[str]:
    suggestions = []
    missing = result["skills"]["missing"]
    kw_missing = result["keywords"]["missing"]
    exp = result["experience"]
    edu = result["education"]
    checks = result["quality"]["checks"]
    priority = result.get("priority", {})

    for skill in missing[:5]:
        suggestions.append(
            f"If you genuinely have experience with {skill}, add concrete evidence of where/how you used it. "
            "Do not add a skill you have not actually used."
        )

    if kw_missing:
        top = ", ".join(k["keyword"] for k in kw_missing[:5])
        suggestions.append(
            f"Review these JD terms and naturally reflect the relevant ones in your summary, skills, "
            f"experience or projects when truthful: {top}."
        )

    if exp["required_years"] is not None and exp["relevant_years_detected"] < exp["required_years"]:
        suggestions.append(
            "Make relevant experience easier to verify: use clear month/year dates, job titles, "
            "and achievement bullets tied directly to the target role."
        )

    exp_domains = exp.get("experience_domain_requirements", {})
    if exp_domains.get("missing"):
        suggestions.append(
            "The JD explicitly asks for experience in these business area(s): "
            + ", ".join(exp_domains["missing"])
            + ". If your actual work history includes them, make that industry/business-area evidence explicit."
        )

    if edu["degree_match"] is False or edu["field_match"] is False:
        suggestions.append(
            "The detected education does not fully match the JD. Do not rewrite your qualification; "
            "instead make the exact degree title and major/department clear in the Education section."
        )

    for item in priority.get("unmatched", [])[:3]:
        suggestions.append(
            "Preferred/advantage item not evidenced in the CV: "
            + item["text"]
            + " If you genuinely meet it, add supporting evidence."
        )

    failed = [c for c in checks if not c["passed"]]
    for check in failed[:3]:
        if check["name"] == "Core sections":
            suggestions.append("Use explicit headings such as Skills, Experience, and Education.")
        elif check["name"] == "Readable bullet structure":
            suggestions.append("Turn responsibilities and achievements into concise bullet points.")
        elif check["name"] == "Resume length":
            suggestions.append("Keep the resume focused on relevant, evidence-based content and remove low-value repetition.")
        elif check["name"] == "Email":
            suggestions.append("Include a professional email address in the resume header.")
        elif check["name"] == "Phone":
            suggestions.append("Include a reachable phone number if appropriate.")

    suggestions.append(
        "Where possible, quantify impact instead of listing duties only (for example uptime, capacity, incidents reduced, "
        "equipment maintained, users supported, or process time saved)."
    )
    return list(dict.fromkeys(suggestions))[:12]


def build_interview_questions(result: dict, resume_text: str) -> list[dict]:
    questions = []
    matched = result["skills"]["matched"]
    missing = result["skills"]["missing"]

    for skill in matched[:5]:
        evidence = find_evidence(resume_text, [skill], limit=1)
        questions.append({
            "type": "Resume-based",
            "skill": skill,
            "question": (
                f"Your resume shows {skill}. Describe a real task where you used it, "
                "what you personally did, and the measurable outcome."
            ),
            "evidence": evidence[0] if evidence else None,
        })

    for skill in missing[:3]:
        questions.append({
            "type": "Gap/JD-based",
            "skill": skill,
            "question": (
                f"This role asks for {skill}, but it was not detected in your CV. "
                f"What related experience do you have, and how would you approach work involving {skill}?"
            ),
            "evidence": None,
        })

    exp = result["experience"]
    if exp["required_years"] is not None:
        questions.append({
            "type": "Experience",
            "skill": None,
            "question": (
                f"The JD asks for at least {exp['required_years']:g} years of relevant experience. "
                "Which roles in your CV best demonstrate this requirement?"
            ),
            "evidence": None,
        })

    for item in result.get("priority", {}).get("unmatched", [])[:2]:
        questions.append({
            "type": "Preferred criterion",
            "skill": None,
            "question": (
                "The JD lists this as a preferred/additional advantage: "
                f"“{item['text']}” What relevant experience or certification can you demonstrate?"
            ),
            "evidence": None,
        })

    questions.append({
        "type": "Behavioral",
        "skill": None,
        "question": (
            "Choose one achievement from your CV. What was the problem, what actions did you personally take, "
            "and what measurable result did you achieve?"
        ),
        "evidence": None,
    })
    return questions[:12]
