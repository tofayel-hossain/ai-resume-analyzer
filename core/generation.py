from core.text_utils import find_evidence


def build_explanation(result: dict) -> dict:
    positive = []
    deductions = []

    matched = result["skills"]["matched"]
    missing = result["skills"]["missing"]
    exp = result["experience"]
    sem = result["semantic"]["score"]
    keyword = result["keywords"]["coverage_score"]
    quality = result["quality"]["score"]

    if matched:
        positive.append(
            f"{len(matched)} JD skill(s) matched: {', '.join(matched[:8])}."
        )
    if sem >= 75:
        positive.append(f"Strong semantic alignment between CV and JD ({sem:.0f}%).")
    elif sem >= 60:
        positive.append(f"Moderate semantic alignment between CV and JD ({sem:.0f}%).")
    if keyword >= 70:
        positive.append(f"Good JD keyword coverage ({keyword:.0f}%).")
    if quality >= 75:
        positive.append(f"Resume structure/readability score is strong ({quality:.0f}%).")

    if missing:
        deductions.append(
            f"JD skills not found in the resume: {', '.join(missing[:8])}."
        )
    if exp["required_years"] is not None and exp["relevant_years_detected"] < exp["required_years"]:
        deductions.append(
            f"JD asks for about {exp['required_years']:g}+ years, while the parser detected "
            f"about {exp['relevant_years_detected']:g} relevant years."
        )
    if keyword < 60:
        deductions.append(f"JD keyword coverage is relatively low ({keyword:.0f}%).")
    if sem < 60:
        deductions.append(f"CV↔JD semantic similarity is relatively low ({sem:.0f}%).")
    if quality < 70:
        failed = [c["name"] for c in result["quality"]["checks"] if not c["passed"]]
        if failed:
            deductions.append("Resume-format checks needing attention: " + ", ".join(failed[:4]) + ".")

    if not positive:
        positive.append("The score is based on the measurable matches that were detected.")
    if not deductions:
        deductions.append("No major rule-based deductions were detected by this MVP.")

    return {
        "positive": positive,
        "deductions": deductions,
        "note": (
            "This is an estimated compatibility score from transparent heuristics and NLP; "
            "it is not the score of any specific commercial ATS."
        ),
    }


def build_suggestions(result: dict) -> list[str]:
    suggestions = []
    missing = result["skills"]["missing"]
    kw_missing = result["keywords"]["missing"]
    exp = result["experience"]
    checks = result["quality"]["checks"]

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
            "and achievement bullets tied to the target role."
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
            suggestions.append("Include a reachable phone number if appropriate for your application market.")

    suggestions.append(
        "Where possible, quantify impact (for example: response time reduced, users served, revenue influenced, "
        "accuracy improved, or process time saved) instead of listing duties only."
    )

    # stable de-duplication
    return list(dict.fromkeys(suggestions))[:10]


def build_interview_questions(result: dict, resume_text: str) -> list[dict]:
    questions = []
    matched = result["skills"]["matched"]
    missing = result["skills"]["missing"]

    for skill in matched[:5]:
        evidence = find_evidence(resume_text, [skill], limit=1)
        context = evidence[0] if evidence else None
        q = (
            f"Your resume mentions {skill}. Walk me through the most important project or task where you used it, "
            "the technical decisions you made, and the measurable outcome."
        )
        questions.append({"type": "Resume-based", "skill": skill, "question": q, "evidence": context})

    for skill in missing[:3]:
        questions.append({
            "type": "Gap/JD-based",
            "skill": skill,
            "question": (
                f"This role appears to value {skill}, but it was not detected in your resume. "
                f"What related experience do you have, and how would you approach a task requiring {skill}?"
            ),
            "evidence": None,
        })

    exp = result["experience"]
    if exp["required_years"] is not None:
        questions.append({
            "type": "Experience",
            "skill": None,
            "question": (
                f"The job description asks for about {exp['required_years']:g}+ years of experience. "
                "Which parts of your background are most directly relevant, and what evidence best demonstrates your readiness?"
            ),
            "evidence": None,
        })

    questions.append({
        "type": "Behavioral",
        "skill": None,
        "question": (
            "Choose one resume achievement you are proud of. What was the problem, what actions did you personally take, "
            "what trade-offs did you make, and what was the result?"
        ),
        "evidence": None,
    })

    return questions[:10]
