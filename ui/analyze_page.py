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
        ("Semantic", scores["semantic"]),
        ("Experience", scores["experience"]),
        ("Keywords", scores["keywords"]),
        ("Resume Quality", scores["resume_quality"]),
    ]
    cols = st.columns(5)
    for col, (label, value) in zip(cols, labels):
        with col:
            st.metric(label, f"{value:.0f}%")


def _render_results(result: dict):
    st.divider()

    left, right = st.columns([1, 2.2], gap="large")
    with left:
        score = result["scores"]["overall"]
        st.markdown(
            f"""
            <div class="score-box">
                <div class="score-kicker">Estimated ATS Compatibility</div>
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
            "Weighted estimate: skills 30% + semantic similarity 25% + "
            "experience 20% + keywords 15% + resume quality 10%."
        )
        st.progress(int(round(score)))

    st.subheader("Score breakdown")
    _render_metric_row(result["scores"])

    tabs = st.tabs(
        [
            "Overview",
            "Skills",
            "Keywords",
            "Experience",
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
            st.markdown("#### What reduced the score")
            for item in explanation["deductions"]:
                st.warning(item)

        st.caption(explanation["note"])
        if result["semantic"].get("fallback"):
            st.warning(
                "Sentence Transformer was unavailable, so this run used TF-IDF cosine similarity as a fallback."
            )

    with tabs[1]:
        c1, c2 = st.columns(2, gap="large")
        with c1:
            st.markdown("#### Matched skills")
            if result["skills"]["matched"]:
                for skill in result["skills"]["matched"]:
                    st.write(f"✅ {skill}")
            else:
                st.caption("No catalogued JD skills were matched.")

        with c2:
            st.markdown("#### Missing skills")
            if result["skills"]["missing"]:
                for skill in result["skills"]["missing"]:
                    st.write(f"❌ {skill}")
            else:
                st.caption("No missing catalogued JD skills detected.")

        with st.expander("All detected skills"):
            st.write("**Resume:**", ", ".join(result["skills"]["resume_skills"]) or "None")
            st.write("**JD:**", ", ".join(result["skills"]["jd_skills"]) or "None")

    with tabs[2]:
        st.metric("Keyword coverage", f"{result['keywords']['coverage_score']:.0f}%")
        c1, c2 = st.columns(2, gap="large")
        with c1:
            st.markdown("#### Present JD keywords")
            for item in result["keywords"]["present"]:
                st.write(
                    f"✅ **{item['keyword']}** — resume {item['resume_count']}× / JD {item['jd_count']}×"
                )
        with c2:
            st.markdown("#### Missing JD keywords")
            for item in result["keywords"]["missing"]:
                st.write(f"❌ **{item['keyword']}** — JD {item['jd_count']}×")

    with tabs[3]:
        exp = result["experience"]
        c1, c2, c3 = st.columns(3)
        c1.metric(
            "JD requirement",
            f"{exp['required_years']:g}+ yrs" if exp["required_years"] is not None else "Not explicit",
        )
        c2.metric("Relevant detected", f"{exp['relevant_years_detected']:g} yrs")
        c3.metric("Total detected", f"{exp['total_years_detected']:g} yrs")
        st.caption(
            "Experience matching is heuristic and depends on readable dates plus nearby role/skill context."
        )
        if exp["evidence"]:
            with st.expander("Show evidence snippets"):
                for item in exp["evidence"]:
                    st.code(item, language=None)

    with tabs[4]:
        for i, suggestion in enumerate(result["suggestions"], 1):
            st.markdown(f"**{i}.** {suggestion}")

    with tabs[5]:
        for i, item in enumerate(result["interview_questions"], 1):
            st.markdown(f"**{i}. {item['type']}**")
            st.write(item["question"])
            if item.get("evidence"):
                st.caption("Resume evidence: " + item["evidence"])
            if i != len(result["interview_questions"]):
                st.divider()


def render_analyze_page():
    st.markdown(
        """
        <div class="hero">
            <div class="hero-badge">AI RESUME CHECKER</div>
            <h1>Resume Match Analyzer</h1>
            <p>
                Upload your resume, paste a job description, and get a simple explainable analysis of
                ATS compatibility, skills, keywords, experience, semantic match, improvements, and interview questions.
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
            help=f"Maximum file size in this project: {MAX_FILE_MB} MB.",
        )
        st.caption("Scanned/image-only PDFs are not OCR'd in this MVP.")

    with c2:
        st.markdown("### 2. Paste job description")
        jd_text = st.text_area(
            "Job description",
            height=240,
            placeholder="Paste the complete job description here...",
            label_visibility="collapsed",
        )

    analyze_clicked = st.button(
        "Analyze Resume",
        type="primary",
        use_container_width=True,
    )

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
            with st.spinner("Analyzing your resume..."):
                result = analyze(file_bytes, uploaded.name, jd_text)
            st.session_state["latest_result"] = result
            _render_results(result)

        except ResumeParseError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.exception(exc)

    elif "latest_result" in st.session_state:
        _render_results(st.session_state["latest_result"])
