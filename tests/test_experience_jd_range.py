from core.experience import extract_requirement_details


def test_standalone_experience_range():
    jd = """
Requirements

Education
BSC Engineer/Diploma in Electrical & Electronics Engineering.

Experience

4 to 5 years
The applicants should have experience in the following business area(s): Group of Companies, Telecommunication

Additional Requirements
Age At least 27 years
"""
    result = extract_requirement_details(jd)
    assert result["years"] == 4.0
    assert result["max_years"] == 5.0
    assert result["source"] == "Experience section"
