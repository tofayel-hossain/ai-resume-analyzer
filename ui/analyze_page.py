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
        st.caption(
            "Core score: skills 25% + semantic 20% + experience 20% + "
            "education 15% + keywords 10% + resume quality 10%."
        )
        st.progress(int(round(score)))

    st.subheader("Core requirement breakdown")
    _render_metric_row(result["scores"])

    tabs = st.tabs(
        [
            "Overview",
            "Skills",
            "Education",
            "Experience",
            "Location & Advantages",
            "Keywords",
            "Improvements",
            "Interview",
        ]
    )

    with tabs[0]:
        explanation = result["explanation"]
        c1, c2 = st.columns(2, gap="large")
        with c1:
            st.markdown("#### What matched well")
            for item in explanation["positive"]:
                st.success(item)
        with c2:
            st.markdown("#### Core gaps")
            for item in explanation["deductions"]:
                st.warning(item)

        for note in explanation.get("notes", []):
            st.info(note)
        st.caption(explanation["note"])

        if result["semantic"].get("fallback"):
            st.warning(
                "Sentence Transformer was unavailable, so this run used TF-IDF cosine similarity as a fallback."
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

        section_status = "Found" if exp.get("experience_section_found") else "Not found — fallback scan used"
        st.caption(f"CV experience section: {section_status}")

        if exp.get("requirement_text"):
            with st.expander("Detected JD experience requirement"):
                st.write(exp["requirement_text"])

        jobs = exp.get("detected_jobs", [])
        if jobs:
            with st.expander(f"Detected employment blocks ({len(jobs)})"):
                for i, job in enumerate(jobs, 1):
                    relevance = "Relevant" if job["relevant"] else "Not clearly relevant"
                    st.markdown(f"**{i}. {job['period']} — {job['duration_years']:g} yrs — {relevance}**")
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
        loc = result["location"]
        st.markdown("#### Location alignment")
        c1, c2, c3 = st.columns(3)
        c1.metric("JD location", (loc.get("jd_location") or "Not detected").title())
        c2.metric("CV location", (loc.get("cv_location") or "Not detected").title())
        c3.metric("Alignment", loc.get("status", "Unknown"))
        if loc.get("distance_km") is not None:
            st.caption(f"Approximate area-centroid distance: {loc['distance_km']:.1f} km")
        st.info(loc["note"])

        st.divider()
        priority = result["priority"]
        st.markdown("#### Preferred / Additional Advantage")

        if priority["matched"]:
            st.markdown("##### Evidenced in CV")
            for item in priority["matched"]:
                evidence = ", ".join(item.get("evidence", []))
                st.success(item["text"] + (f"  \nEvidence: {evidence}" if evidence else ""))

        if priority["unmatched"]:
            st.markdown("##### Not evidenced in CV")
            for item in priority["unmatched"]:
                st.warning(item["text"])

        if not priority["matched"] and not priority["unmatched"]:
            st.caption("No non-sensitive preferred/additional-advantage criteria detected.")

        if priority["excluded_sensitive"]:
            st.markdown("##### Excluded from automated matching")
            for item in priority["excluded_sensitive"]:
                st.info(f"{item['text']}  \n{item['reason']}")

    with tabs[5]:
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

    with tabs[6]:
        for i, suggestion in enumerate(result["suggestions"], 1):
            st.markdown(f"**{i}.** {suggestion}")

    with tabs[7]:
        for i, item in enumerate(result["interview_questions"], 1):
            st.markdown(f"**{i}. {item['type']}**")
            st.write(item["question"])
            if item.get("evidence"):
                st.caption("CV evidence: " + item["evidence"])
            if i != len(result["interview_questions"]):
                st.divider()


def render_analyze_page():
    st.markdown(
        """
        <div class="hero">
            <div class="hero-badge">AI RESUME CHECKER</div>
            <h1>Resume Match Analyzer</h1>
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
            with st.spinner("Comparing CV requirements with the job description..."):
                result = analyze(file_bytes, uploaded.name, jd_text)
            st.session_state["latest_result"] = result
            _render_results(result)
        except ResumeParseError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.exception(exc)

    elif "latest_result" in st.session_state:
        _render_results(st.session_state["latest_result"])
