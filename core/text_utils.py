import re
from typing import Iterable


SECTION_ALIASES = {
    "summary": ["summary", "professional summary", "profile", "objective"],
    "skills": ["skills", "technical skills", "core competencies", "technologies"],
    "experience": ["experience", "work experience", "professional experience", "employment", "employment history", "work history", "career history", "professional background", "relevant experience"],
    "education": ["education", "academic background", "qualifications"],
    "projects": ["projects", "selected projects", "academic projects", "personal projects"],
    "certifications": ["certifications", "certificates", "licenses"],
}


def clean_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def normalize_token(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9+#./ -]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def detect_sections(text: str) -> dict[str, bool]:
    lower = text.lower()
    found = {}
    for section, aliases in SECTION_ALIASES.items():
        found[section] = any(
            re.search(rf"(?im)^\s*{re.escape(alias)}\s*:?\s*$", lower)
            for alias in aliases
        )
    return found


def sentences(text: str) -> list[str]:
    chunks = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [c.strip() for c in chunks if len(c.strip()) >= 20]


def find_evidence(text: str, terms: Iterable[str], limit: int = 5) -> list[str]:
    out = []
    term_list = [t.lower() for t in terms if t]
    for sentence in sentences(text):
        low = sentence.lower()
        if any(term in low for term in term_list):
            clipped = sentence[:220] + ("…" if len(sentence) > 220 else "")
            if clipped not in out:
                out.append(clipped)
        if len(out) >= limit:
            break
    return out
