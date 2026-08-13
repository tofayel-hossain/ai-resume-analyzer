import re

from core.ats import overall_score, resume_quality_score
from core.experience import experience_match
from core.file_parser import extract_resume_text
from core.generation import build_explanation, build_interview_questions, build_suggestions
from core.keyword_analyzer import keyword_analysis
from core.semantic import semantic_similarity
from core.skills import match_skills
from core.text_utils import clean_text


def extract_job_title(jd_text: str) -> str:
    lines = [line.strip() for line in jd_text.splitlines() if line.strip()]
    role_terms = (
        "engineer", "developer", "analyst", "scientist", "manager", "designer",
        "architect", "specialist", "administrator", "intern", "consultant",
    )
    for line in lines[:10]:
        low = line.lower()
        if any(term in low for term in role_terms) and len(line) <= 100:
            line = re.sub(r"^(job\s*title|position|role)\s*:\s*", "", line, flags=re.I)
            return line[:100]
    return "Target Role"


def analyze(file_bytes: bytes, filename: str, jd_text: str) -> dict:
    resume_raw = extract_resume_text(file_bytes, filename)
    resume_text = clean_text(resume_raw)
    jd_text = clean_text(jd_text)

    skills = match_skills(resume_text, jd_text)
    keywords = keyword_analysis(resume_text, jd_text)
    semantic = semantic_similarity(resume_text, jd_text)
    experience = experience_match(resume_text, jd_text, skills["jd_skills"])
    quality = resume_quality_score(resume_text)

    skill_score = skills["score"]
    if skill_score is None:
        # When no catalogued skills are found in the JD, use keyword coverage
        # rather than forcing the skill component to zero.
        skill_score = keywords["coverage_score"]
        skills["score"] = skill_score
        skills["score_fallback"] = "keyword coverage"

    final = overall_score(
        skill_score=skill_score,
        semantic_score=semantic["score"],
        experience_score=experience["score"],
        keyword_score=keywords["coverage_score"],
        quality_score=quality["score"],
    )

    result = {
        "job_title": extract_job_title(jd_text),
        "resume_filename": filename,
        "resume_text": resume_text,
        "job_description": jd_text,
        "skills": skills,
        "keywords": keywords,
        "semantic": semantic,
        "experience": experience,
        "quality": quality,
        "scores": {
            "overall": final,
            "skills": round(skill_score, 1),
            "semantic": semantic["score"],
            "experience": experience["score"],
            "keywords": keywords["coverage_score"],
            "resume_quality": quality["score"],
        },
    }

    result["explanation"] = build_explanation(result)
    result["suggestions"] = build_suggestions(result)
    result["interview_questions"] = build_interview_questions(result, resume_text)

    return result
