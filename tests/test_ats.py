from core.ats import overall_score


def test_overall_score():
    result = overall_score(
        skill_score=80,
        semantic_score=80,
        experience_score=80,
        education_score=80,
        keyword_score=80,
        quality_score=80,
    )
    assert result == 80.0
