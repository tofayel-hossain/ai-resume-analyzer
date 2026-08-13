from core.experience import extract_required_years, experience_match


def test_jd_requirement_variants():
    assert extract_required_years("Minimum 3+ years of software development experience is required.") == 3
    assert extract_required_years("You should have at least three years of relevant experience with Python.") == 3
    assert extract_required_years("We require 3-5 years of professional experience in backend systems.") == 3
    assert extract_required_years("Candidates need experience of at least 4 years in software engineering.") == 4


def test_education_year_is_not_experience_requirement():
    jd = "Bachelor degree from a 4 year university program. Python knowledge is preferred."
    assert extract_required_years(jd) is None


def test_experience_section_and_relevance():
    resume = """
    Jane Doe

    SKILLS
    Python, FastAPI, PostgreSQL, Docker

    WORK EXPERIENCE
    Backend Developer
    ABC Technologies Ltd
    Jan 2022 - Present
    Developed REST APIs using Python, FastAPI and PostgreSQL.
    Deployed services with Docker.

    EDUCATION
    BSc in Computer Science
    2017 - 2021
    """
    jd = """
    Backend Developer
    We are looking for a backend developer with minimum 3+ years of software development experience.
    Required skills: Python, FastAPI, PostgreSQL, Docker.
    """

    result = experience_match(resume, jd, ["Python", "FastAPI", "PostgreSQL", "Docker"])

    assert result["required_years"] == 3
    assert result["experience_section_found"] is True
    assert result["relevant_years_detected"] >= 3
    assert result["total_years_detected"] == result["relevant_years_detected"]
    assert result["detected_jobs"][0]["relevant"] is True
