import streamlit as st

from ui.analyze_page import render_analyze_page

st.set_page_config(
    page_title="AI Resume Intelligence",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    :root {
        --red-50: #fff7f7;
        --red-100: #ffe8e8;
        --red-200: #ffcfcf;
        --red-500: #e5484d;
        --red-600: #cf3f44;
        --red-700: #b9353a;
        --text: #2a1b1c;
        --muted: #7d6567;
        --border: #f0d7d8;
        --card: #ffffff;
    }

    .stApp {
        background: linear-gradient(180deg, #fffafa 0%, #ffffff 34%, #fffafa 100%);
        color: var(--text);
    }

    .block-container {
        max-width: 1100px;
        padding-top: 2.2rem;
        padding-bottom: 3rem;
    }

    [data-testid="stSidebar"] { display: none; }

    .hero {
        background: linear-gradient(135deg, #fff7f7 0%, #ffffff 65%);
        border: 1px solid var(--border);
        border-radius: 22px;
        padding: 1.8rem 1.9rem;
        margin-bottom: 1.25rem;
        box-shadow: 0 10px 35px rgba(185, 53, 58, 0.06);
    }

    .hero-badge {
        display: inline-block;
        padding: .35rem .7rem;
        border-radius: 999px;
        background: var(--red-100);
        color: var(--red-700);
        font-size: .78rem;
        font-weight: 700;
        letter-spacing: .02em;
        margin-bottom: .7rem;
    }

    .hero h1 {
        margin: 0 0 .35rem 0;
        font-size: clamp(2rem, 4vw, 3rem);
        line-height: 1.05;
        color: #521f22;
    }

    .hero p {
        margin: 0;
        color: var(--muted);
        font-size: 1rem;
        max-width: 760px;
    }

    .section-card {
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: 18px;
        padding: 1rem 1.1rem;
        box-shadow: 0 8px 24px rgba(185, 53, 58, 0.04);
    }

    .score-box {
        background: linear-gradient(145deg, #fff7f7, #ffffff);
        border: 1px solid var(--red-200);
        border-radius: 20px;
        padding: 1.35rem 1rem;
        text-align: center;
        box-shadow: 0 12px 30px rgba(185, 53, 58, 0.07);
    }

    .score-kicker {
        font-size: .82rem;
        color: var(--muted);
        margin-bottom: .3rem;
    }

    .score-number {
        font-size: 3.3rem;
        font-weight: 800;
        line-height: 1;
        color: var(--red-700);
    }

    .score-label {
        margin-top: .5rem;
        color: #67383b;
        font-weight: 600;
    }

    div[data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid var(--border);
        border-radius: 16px;
        padding: .8rem .9rem;
    }

    div[data-testid="stFileUploader"],
    div[data-testid="stTextArea"] {
        border-radius: 16px;
    }

    .stButton > button {
        width: 100%;
        border-radius: 12px;
        border: 1px solid var(--red-600);
        background: var(--red-600);
        color: white;
        font-weight: 700;
        min-height: 46px;
        box-shadow: none;
    }

    .stButton > button:hover {
        background: var(--red-700);
        border-color: var(--red-700);
        color: white;
    }

    div[data-baseweb="tab-list"] {
        gap: .35rem;
    }

    button[data-baseweb="tab"] {
        border-radius: 10px;
    }

    .small-note {
        font-size: .86rem;
        color: var(--muted);
    }

    @media (max-width: 768px) {
        .block-container { padding-top: 1rem; }
        .hero { padding: 1.25rem; border-radius: 18px; }
        .score-number { font-size: 2.8rem; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

render_analyze_page()
