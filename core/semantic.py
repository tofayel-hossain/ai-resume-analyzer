import os
from functools import lru_cache

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from config import SEMANTIC_MODEL


def _chunks(text: str, max_chars: int = 1400, max_chunks: int = 16) -> list[str]:
    paragraphs = [p.strip() for p in text.splitlines() if p.strip()]
    chunks = []
    buf = ""
    for p in paragraphs:
        if len(buf) + len(p) + 1 <= max_chars:
            buf = f"{buf}\n{p}".strip()
        else:
            if buf:
                chunks.append(buf)
            buf = p[:max_chars]
        if len(chunks) >= max_chunks:
            break
    if buf and len(chunks) < max_chunks:
        chunks.append(buf)
    return chunks or [text[:max_chars]]


@lru_cache(maxsize=1)
def _load_model():
    # Model download happens on first use if not already cached locally.
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(SEMANTIC_MODEL)


def _sentence_transformer_score(resume_text: str, jd_text: str) -> float:
    model = _load_model()
    resume_chunks = _chunks(resume_text)
    jd_chunks = _chunks(jd_text)

    r = model.encode(resume_chunks, normalize_embeddings=True, show_progress_bar=False)
    j = model.encode(jd_chunks, normalize_embeddings=True, show_progress_bar=False)

    # Pairwise cosine because embeddings are normalized.
    sims = np.matmul(r, j.T)

    # For each JD chunk, take its best resume match, then average.
    best_per_jd = sims.max(axis=0)
    raw = float(best_per_jd.mean())

    # Cosine can be negative. Present a bounded 0-100 score.
    return round(max(0.0, min(1.0, raw)) * 100, 1)


def _tfidf_fallback(resume_text: str, jd_text: str) -> float:
    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), max_features=5000)
    matrix = vectorizer.fit_transform([resume_text, jd_text])
    score = float(cosine_similarity(matrix[0:1], matrix[1:2])[0][0])
    return round(max(0.0, min(1.0, score)) * 100, 1)


def semantic_similarity(resume_text: str, jd_text: str) -> dict:
    try:
        score = _sentence_transformer_score(resume_text, jd_text)
        return {
            "score": score,
            "engine": f"Sentence Transformers ({SEMANTIC_MODEL})",
            "fallback": False,
        }
    except Exception as exc:
        score = _tfidf_fallback(resume_text, jd_text)
        return {
            "score": score,
            "engine": "TF-IDF cosine fallback",
            "fallback": True,
            "warning": str(exc)[:300],
        }


def semantic_requirement_matches(requirements: list[str], job_blocks: list[str]) -> list[dict]:
    """
    Batch-match each JD requirement against the best CV employment block.
    Returns 0-100 similarity scores and the best block index.
    """
    if not requirements:
        return []
    if not job_blocks:
        return [
            {"requirement": req, "score": 0.0, "best_block_index": None, "engine": "No employment block"}
            for req in requirements
        ]

    try:
        model = _load_model()
        req_embeddings = model.encode(requirements, normalize_embeddings=True, show_progress_bar=False)
        job_embeddings = model.encode(job_blocks, normalize_embeddings=True, show_progress_bar=False)
        matrix = np.matmul(req_embeddings, job_embeddings.T)
        out = []
        for i, req in enumerate(requirements):
            idx = int(np.argmax(matrix[i]))
            score = float(matrix[i][idx])
            out.append({
                "requirement": req,
                "score": round(max(0.0, min(1.0, score)) * 100, 1),
                "best_block_index": idx,
                "engine": f"Sentence Transformers ({SEMANTIC_MODEL})",
            })
        return out
    except Exception:
        # TF-IDF fallback. Fit all requirements and employment blocks in one vocabulary.
        corpus = requirements + job_blocks
        try:
            vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), max_features=7000)
            matrix = vectorizer.fit_transform(corpus)
            req_matrix = matrix[:len(requirements)]
            job_matrix = matrix[len(requirements):]
            sims = cosine_similarity(req_matrix, job_matrix)
            out = []
            for i, req in enumerate(requirements):
                idx = int(np.argmax(sims[i]))
                out.append({
                    "requirement": req,
                    "score": round(float(sims[i][idx]) * 100, 1),
                    "best_block_index": idx,
                    "engine": "TF-IDF cosine fallback",
                })
            return out
        except Exception:
            return [
                {"requirement": req, "score": 0.0, "best_block_index": None, "engine": "Unavailable"}
                for req in requirements
            ]