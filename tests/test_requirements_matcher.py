from core.requirements_matcher import (
    build_jd_skill_text,
    education_match,
    location_match,
    priority_requirements_match,
)
from core.skills import match_skills


JD = """
Requirements

Education

BSC Engineer/Diploma in Electrical & Electronics Engineering (EEE), Electronics and Communication Engineering (ECE) or Mechanical Engineering from any UGC approved university.
Experience

4 to 5 years
The applicants should have experience in the following business area(s): Group of Companies, Telecommunication
Additional Requirements

Age At least 27 years
Responsibilities & Context

Responsibilities:

Experience on Operation and Maintenance of electrical systems at data center.
Experience on basic Operation and Maintenance of Precision AC (PAC)
Experience on basic Operation and Maintenance of High capacity UPS (200+ KW UPS)
Experience on basic Operation and Maintenance of Diesel Generator (400+ KVA DG)
Experience of commissioning, testing and maintenance work of Fire protection & Detection system.
Working experience on PFI, LT and HT panel, HVAC, Building power management and wiring like BMS etc.
Installation experience of Server, router, switch and other IT equipment in Datacenter rack.
Working experience in Datacenter will be considered as added advantage.
Certification on CDCP/CDFOM or any other certification related to Datacenter will be an added advantage.
Non-Muslim candidate will get additional advantage.

Skills & Expertise
Data centre
Data NOC
NOC
Other Relevant Skills

Operation & Maintenance
Job Location

Dhaka (Mohakhali)
"""

CV = """
Md Example
Mirpur, Dhaka
example@email.com

EDUCATION
B.Sc. in Electrical and Electronic Engineering (EEE)
Example University

EXPERIENCE
Electrical Engineer
Jan 2022 - Present
Operation and Maintenance of electrical systems at a data center.
Maintained UPS, Diesel Generator, HVAC, LT Panel, HT Panel and BMS.
Installed server, router and network switch equipment.
Worked with NOC and fire detection systems.

SKILLS
Electrical Systems, Data Center, NOC, UPS, HVAC, BMS, Microsoft Excel
"""


def test_education_requirement_match():
    result = education_match(CV, JD)
    assert result["degree_match"] is True
    assert result["field_match"] is True
    assert result["requires_ugc_approved"] is True
    assert result["score"] == 100.0


def test_location_nearby():
    result = location_match(CV, JD)
    assert result["jd_location"] == "mohakhali"
    assert result["cv_location"] == "mirpur"
    assert result["status"] in {"Nearby", "Same city"}
    assert result["distance_km"] is not None


def test_priority_and_sensitive_exclusion():
    result = priority_requirements_match(CV, JD)
    texts = [x["text"].lower() for x in result["matched"]]
    assert any("datacenter" in x for x in texts)
    unmatched = " ".join(x["text"].lower() for x in result["unmatched"])
    assert "cdcp/cdfom" in unmatched
    excluded = " ".join(x["text"].lower() for x in result["excluded_sensitive"])
    assert "non-muslim" in excluded
    assert "age at least 27" in excluded


def test_requirement_skill_matching():
    skill_text = build_jd_skill_text(JD)["text"]
    result = match_skills(CV, skill_text)
    assert "Data Center" in result["matched"]
    assert "NOC" in result["matched"]
    assert "UPS" in result["matched"]
    assert "HVAC" in result["matched"]


def test_business_area_requirement_is_core_experience():
    from core.requirements_matcher import match_experience_domain_requirements
    result = match_experience_domain_requirements(CV, JD)
    assert "Telecommunication" in result["required"]
    assert "Group of Companies" in result["required"]
    assert result["score"] == 0.0
