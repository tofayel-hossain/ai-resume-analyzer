import streamlit as st

from config import MAX_FILE_MB
from core.file_parser import ResumeParseError
from core.pipeline import analyze


def _score_label(score: float) -> str:
    if score >= 85:
        return "Very strong match"
    if score >= 70:
        return "Strong match"
    if score >= 55:
        return "Moderate match"
    return "Needs improvement"


def _render_metric_row(scores: dict):
    labels = [
        ("Skills", scores["skills"]),
        ("Experience", scores["experience"]),
        ("Education", scores["education"]),
        ("Semantic", scores["semantic"]),
        ("Keywords", scores["keywords"]),
        ("Resume Quality", scores["resume_quality"]),
    ]
    cols = st.columns(3)
    for i, (label, value) in enumerate(labels):
        with cols[i % 3]:
            st.metric(label, f"{value:.0f}%")


def _yes_no(value):
    if value is True:
        return "✅ Matched"
    if value is False:
        return "❌ Not matched"
    return "— Not explicit"


def _render_results(result: dict):
    st.divider()

    left, right = st.columns([1, 2.2], gap="large")
    with left:
        score = result["scores"]["overall"]
        st.markdown(
            f"""
            <div class="score-box">
                <div class="score-kicker">Estimated Compatibility</div>
                <div class="score-number">{score:.0f}%</div>
                <div class="score-label">{_score_label(score)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with right:
        st.subheader(result["job_title"])
        st.write(f"Resume: **{result['resume_filename']}**")
        st.progress(int(round(score)))

    st.subheader("Core requirement breakdown")
    _render_metric_row(result["scores"])

    tabs = st.tabs(
        [
            "Overview",
            "Skills",
            "Education",
            "Experience",
            "Location",
            "Additional Advantages",
            "Age",
            "Keywords",
            "Improvements",
            "Interview Preparation",
        ]
    )

    with tabs[0]:
        st.markdown("#### What matched well")

        st.success(f"{len(result['skills']['matched'])} job-related skills matched")

        education = result.get("education", {})
        if education.get("score", 0) >= 80:
            st.success("Education requirement fulfilled")

        if result["scores"]["resume_quality"] >= 75:
            st.success("Resume structure is strong")

        advantages = result.get("advantages", {})
        matched_advantages = advantages.get("matched", [])
        if matched_advantages:
            st.success(
                f"{len(matched_advantages)} additional advantage(s) matched"
            )

        location = result.get("location", {})
        if location.get("status") in ["Nearby", "Same area", "Same city"]:
            st.success(f"Location is {location.get('status').lower()}")

        st.markdown("#### Core gaps")

        if result["skills"]["missing"]:
            st.warning("Some required skills are missing")

        experience = result.get("experience", {})
        if experience.get("missing_business_areas"):
            st.warning(
                "Required business-area experience was not found"
            )

        if result["scores"]["keywords"] < 60:
            st.warning("Keyword coverage is moderate")

        if result["scores"]["semantic"] < 60:
            st.warning("CV and JD semantic match is moderate")

        st.caption(
            "This is an estimated compatibility score based on transparent rules and NLP."
        )

    with tabs[1]:
        st.markdown("#### Requirement skills vs CV skills")
        st.caption(
            "JD skills are extracted from requirement-bearing sections such as Skills & Expertise, "
            "Other Relevant Skills, Responsibilities, and Additional Requirements."
        )
        c1, c2 = st.columns(2, gap="large")
        with c1:
            st.markdown("##### Matched")
            if result["skills"]["matched"]:
                for skill in result["skills"]["matched"]:
                    st.write(f"✅ {skill}")
            else:
                st.caption("No catalogued requirement skills matched.")
        with c2:
            st.markdown("##### Missing")
            if result["skills"]["missing"]:
                for skill in result["skills"]["missing"]:
                    st.write(f"❌ {skill}")
            else:
                st.caption("No missing catalogued requirement skills detected.")

        with st.expander("All detected skills"):
            st.write("**CV skills:**", ", ".join(result["skills"]["resume_skills"]) or "None")
            st.write("**JD requirement skills:**", ", ".join(result["skills"]["jd_skills"]) or "None")

        sections = result["requirements"]["skill_requirements"]["sections"]
        with st.expander("JD sections used for skill matching"):
            for name, body in sections.items():
                if body:
                    st.markdown(f"**{name}**")
                    st.code(body, language=None)

    with tabs[2]:
        edu = result["education"]
        st.metric("Education match", f"{edu['score']:.0f}%")
        st.write(f"**Status:** {edu['status']}")

        c1, c2 = st.columns(2, gap="large")
        with c1:
            st.markdown("##### JD education requirement")
            st.write("**Accepted degree(s):**", ", ".join(edu["required_degrees"]) or "Not explicitly detected")
            st.write("**Accepted field(s):**", ", ".join(edu["accepted_fields"]) or "Not explicitly detected")
            if edu["requires_ugc_approved"]:
                st.write("**Institution condition:** UGC/approved institution mentioned")
        with c2:
            st.markdown("##### CV education detected")
            st.write("**Degree(s):**", ", ".join(edu["cv_degrees"]) or "Not detected")
            st.write("**Field(s):**", ", ".join(edu["cv_fields"]) or "Not detected")
            st.write("**Degree:**", _yes_no(edu["degree_match"]))
            st.write("**Field:**", _yes_no(edu["field_match"]))

        if edu.get("institution_verification"):
            st.info(
                "Institution approval: Needs external verification. "
                "This offline app does not assume whether a university is currently UGC-approved."
            )

        if edu.get("jd_text"):
            with st.expander("Detected JD Education section"):
                st.code(edu["jd_text"], language=None)
        if edu.get("resume_text"):
            with st.expander("Detected CV Education section"):
                st.code(edu["resume_text"], language=None)

    with tabs[3]:
        exp = result["experience"]
        c1, c2, c3 = st.columns(3)
        if exp["required_years"] is None:
            requirement_label = "Not explicit"
        elif exp.get("max_required_years") is not None:
            requirement_label = f"{exp['required_years']:g}–{exp['max_required_years']:g} yrs"
        else:
            requirement_label = f"{exp['required_years']:g}+ yrs"

        c1.metric("JD requirement", requirement_label)
        c2.metric("Relevant detected", f"{exp['relevant_years_detected']:g} yrs")
        c3.metric("Total detected", f"{exp['total_years_detected']:g} yrs")

        domains = exp.get("experience_domain_requirements", {})
        if domains.get("required"):
            st.markdown("##### Required business-area experience")
            dc1, dc2 = st.columns(2)
            with dc1:
                st.write("**Matched:**", ", ".join(domains.get("matched", [])) or "None")
            with dc2:
                st.write("**Not evidenced:**", ", ".join(domains.get("missing", [])) or "None")
            if domains.get("score") is not None:
                st.caption(
                    f"Business-area match: {domains['score']:.0f}%. "
                    "Experience score combines years (75%) and explicit business-area match (25%) when such a requirement exists."
                )

        section_status = "Found" if exp.get("experience_section_found") else "Not found!! fallback scan used"
        st.caption(f"CV experience section: {section_status}")

        if exp.get("requirement_text"):
            with st.expander("Detected JD experience requirement"):
                st.write(exp["requirement_text"])

        jobs = exp.get("detected_jobs", [])
        if jobs:
            with st.expander(f"Detected employment blocks ({len(jobs)})"):
                for i, job in enumerate(jobs, 1):
                    relevance = "Relevant" if job["relevant"] else "Not clearly relevant"
                    st.markdown(f"**{i}. {job['period']} - {job['duration_years']:g} yrs - {relevance}**")
                    if job.get("matched_skills"):
                        st.caption("Matched skills: " + ", ".join(job["matched_skills"]))
                    if job.get("matched_role_terms"):
                        st.caption("Matched role terms: " + ", ".join(job["matched_role_terms"]))
                    if job.get("matched_domain_terms"):
                        st.caption("Matched JD terms: " + ", ".join(job["matched_domain_terms"]))
                    if job.get("jd_similarity") is not None:
                        st.caption(f"Employment block ↔ JD similarity: {job['jd_similarity']:.1f}%")
                    st.code(job["block"], language=None)

        st.caption(
            "Experience matching uses employment dates plus nearby role, skill, domain-term and JD-text evidence."
        )

    with tabs[4]:
        st.markdown("#### Location")

        location = result.get("location", {})

        c1, c2, c3 = st.columns(3)

        c1.metric(
            "Job Location",
            location.get("jd_location") or "Not detected"
        )

        c2.metric(
            "CV Location",
            location.get("cv_location") or "Not detected"
        )

        c3.metric(
            "Status",
            location.get("status") or "Unknown"
        )
        
    with tabs[5]:
        st.markdown("#### Additional Advantages")

        advantages = result.get("advantages", {})

        matched = advantages.get("matched", [])
        missing = advantages.get("missing", [])

        if matched:
            st.markdown("**Matched**")

            for item in matched:
                st.write(f"✅ {item}")

        if missing:
            st.markdown("**Not found in CV**")

            for item in missing:
                st.write(f"⚪ {item}")

        if not matched and not missing:
            st.caption(
                "No additional advantage requirements detected."
            )
    
    with tabs[6]:
        st.markdown("#### Age Information")

        age_info = result.get(
            "age_information",
            {},
        )

        jd_requirement = (
            age_info.get("jd_requirement")
            or "Not explicitly detected"
        )

        cv_dob = (
            age_info.get("cv_dob")
            or "Not detected"
        )

        calculated_age = age_info.get(
            "calculated_age"
        )

        if calculated_age is None:
            age_display = "Not available"
        else:
            age_display = f"{calculated_age} years"

        c1, c2, c3 = st.columns(3)

        c1.metric(
            "JD Age Requirement",
            jd_requirement,
        )

        c2.metric(
            "CV Date of Birth",
            cv_dob,
        )

        c3.metric(
            "Calculated Age",
            age_display,
        )

        if not age_info.get(
            "jd_requirement_detected"
        ):
            st.caption(
                "No explicit age requirement was detected "
                "in the Job Description."
            )

        elif not age_info.get(
            "cv_dob_detected"
        ):
            st.caption(
                "A Job Description age requirement was detected, "
                "but no explicit Date of Birth was found in the CV."
            )

        else:
            st.info(
                "Age information is calculated from your CV."
            )
    
    with tabs[7]:
        st.metric("Keyword coverage", f"{result['keywords']['coverage_score']:.0f}%")
        c1, c2 = st.columns(2, gap="large")
        with c1:
            st.markdown("#### Present JD keywords")
            for item in result["keywords"]["present"]:
                st.write(
                    f"✅ **{item['keyword']}** — CV {item['resume_count']}× / JD {item['jd_count']}×"
                )
        with c2:
            st.markdown("#### Missing JD keywords")
            for item in result["keywords"]["missing"]:
                st.write(f"❌ **{item['keyword']}** — JD {item['jd_count']}×")

    with tabs[8]:
        for i, suggestion in enumerate(result["suggestions"], 1):
            st.markdown(f"**{i}.** {suggestion}")

    with tabs[9]:
        for i, item in enumerate(result["interview_questions"], 1):
            st.markdown(f"**{i}. {item['type']}**")
            st.write(item["question"])
            if i != len(result["interview_questions"]):
                st.divider()


def render_analyze_page():
    st.markdown(
        """
        <div class="hero">
            <div class="hero-badge">Analyzer</div>
            <h1>AI Resume Analyzer</h1>
            <p>
                Compare CV requirements against a job description: skills, experience, education,
                location alignment, preferred criteria, semantic similarity and explainable score.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns([1, 1.25], gap="large")
    with c1:
        st.markdown("### 1. Upload resume")
        uploaded = st.file_uploader(
            "PDF or DOCX",
            type=["pdf", "docx"],
            help=f"Maximum file size: {MAX_FILE_MB} MB.",
        )
        st.caption("Scanned/image-only PDFs are not OCR'd in this version.")

    with c2:
        st.markdown("### 2. Paste job description")
        jd_text = st.text_area(
            "Job description",
            height=260,
            placeholder="Paste the complete job description here...",
            label_visibility="collapsed",
        )

    analyze_clicked = st.button("Analyze Resume", type="primary", use_container_width=True)

    if analyze_clicked:
        if not uploaded:
            st.error("Please upload a PDF or DOCX resume.")
            return
        if not jd_text.strip() or len(jd_text.strip()) < 80:
            st.error("Please paste a reasonably complete job description.")
            return

        file_bytes = uploaded.getvalue()
        if len(file_bytes) > MAX_FILE_MB * 1024 * 1024:
            st.error(f"File is larger than the configured {MAX_FILE_MB} MB limit.")
            return

        try:
            status_text = st.empty()
            progress_bar = st.progress(0)

            def show_progress(percent, message):
                progress_bar.progress(percent)
                status_text.markdown(f"**{message}**")

            result = analyze(
                file_bytes,
                uploaded.name,
                jd_text,
                progress_callback=show_progress,
            )

            st.session_state["latest_result"] = result

            progress_bar.empty()
            status_text.empty()

            _render_results(result)

        except ResumeParseError as exc:
            st.error(str(exc))

        except Exception as exc:
            st.exception(exc)

    elif "latest_result" in st.session_state:
        _render_results(st.session_state["latest_result"])
