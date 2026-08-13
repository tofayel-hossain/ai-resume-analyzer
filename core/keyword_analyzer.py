import re
from collections import Counter

from sklearn.feature_extraction.text import CountVectorizer


GENERIC_TERMS = {
    "experience", "work", "working", "job", "role", "candidate", "team",
    "company", "skills", "skill", "required", "requirements", "preferred",
    "responsibilities", "responsibility", "ability", "strong", "excellent",
    "knowledge", "including", "using", "years", "year", "business",
}


def _normalize_phrase(phrase: str) -> str:
    return re.sub(r"\s+", " ", phrase.lower().strip())


def extract_jd_keywords(jd_text: str, max_features: int = 30) -> list[tuple[str, int]]:
    vectorizer = CountVectorizer(
        stop_words="english",
        ngram_range=(1, 2),
        max_features=80,
        token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z0-9+#./-]{1,}\b",
    )
    try:
        matrix = vectorizer.fit_transform([jd_text])
    except ValueError:
        return []

    names = vectorizer.get_feature_names_out()
    counts = matrix.toarray()[0]
    pairs = []
    for name, count in zip(names, counts):
        normalized = _normalize_phrase(name)
        if normalized in GENERIC_TERMS:
            continue
        if len(normalized) < 3:
            continue
        pairs.append((normalized, int(count)))

    # Prefer higher frequency and useful two-word phrases.
    pairs.sort(key=lambda x: (x[1], len(x[0].split()), len(x[0])), reverse=True)

    deduped = []
    seen = set()
    for phrase, count in pairs:
        if phrase in seen:
            continue
        # Avoid keeping a unigram when a stronger bigram already contains it.
        if len(phrase.split()) == 1 and any(
            phrase in existing.split() for existing, _ in deduped[:10]
        ):
            continue
        seen.add(phrase)
        deduped.append((phrase, count))
        if len(deduped) >= max_features:
            break
    return deduped


def keyword_analysis(resume_text: str, jd_text: str) -> dict:
    keywords = extract_jd_keywords(jd_text)
    resume_lower = resume_text.lower()

    present = []
    missing = []
    weighted_hit = 0
    weighted_total = 0

    for phrase, jd_count in keywords:
        resume_count = len(re.findall(re.escape(phrase), resume_lower, flags=re.I))
        weight = min(jd_count, 3)
        weighted_total += weight
        if resume_count > 0:
            weighted_hit += weight
            present.append(
                {"keyword": phrase, "jd_count": jd_count, "resume_count": resume_count}
            )
        else:
            missing.append(
                {"keyword": phrase, "jd_count": jd_count, "resume_count": 0}
            )

    coverage = round((weighted_hit / weighted_total) * 100, 1) if weighted_total else 0.0

    resume_words = re.findall(r"\b[a-zA-Z][a-zA-Z0-9+#./-]{2,}\b", resume_lower)
    repeated = [
        {"keyword": word, "resume_count": count}
        for word, count in Counter(resume_words).most_common(20)
        if count >= 3 and word not in GENERIC_TERMS
    ][:10]

    return {
        "coverage_score": coverage,
        "present": present[:15],
        "missing": missing[:15],
        "repeated": repeated,
        "jd_keywords": [{"keyword": k, "jd_count": c} for k, c in keywords],
    }
