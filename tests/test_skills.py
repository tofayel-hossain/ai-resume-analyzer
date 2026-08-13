from core.skills import match_skills


def test_skill_match():
    resume = "Python, FastAPI, PostgreSQL and Git."
    jd = "We need Python, FastAPI, PostgreSQL, Docker and AWS."
    result = match_skills(resume, jd)

    assert "Python" in result["matched"]
    assert "FastAPI" in result["matched"]
    assert "Docker" in result["missing"]
    assert result["score"] == 60.0
