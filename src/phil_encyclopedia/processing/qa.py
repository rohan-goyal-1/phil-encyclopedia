from __future__ import annotations

import re
from dataclasses import dataclass, field

from pydantic import ValidationError

from .models import GeneratedArticle

SENSITIVE_PATTERNS = [
    r"\babortion\b",
    r"\brace\b|\bracism\b|\bracial\b",
    r"\breligion\b|\bgod\b|\btheism\b|\batheism\b",
    r"\bviolence\b|\bwar\b|\bterror\b",
    r"\bsex\b|\bsexuality\b|\bgender\b",
    r"\bdeath\b|\bsuicide\b|\bmurder\b",
    r"\bpolitic(?:s|al|s)?\b|\bideology\b|\bfascis[mt]\b|\bcommunis[mt]\b",
]


@dataclass(frozen=True)
class QAResult:
    passed: bool
    status: str
    notes: list[str] = field(default_factory=list)
    article: GeneratedArticle | None = None


def validate_generated_payload(payload: object, source_text: str = "") -> QAResult:
    notes: list[str] = []
    try:
        article = GeneratedArticle.model_validate(payload)
    except ValidationError as exc:
        return QAResult(False, "failed", [f"schema validation failed: {exc.errors()}"])

    combined = _combined_generated_text(article)
    copied = detect_copied_passages(combined, source_text)
    if copied:
        notes.append(f"possible copied source passage: {copied[0][:120]}")
    if detects_hallucinated_citations(combined):
        notes.append("possible hallucinated citation detected")

    sensitive_reasons = sensitive_topic_reasons(article, combined)
    if sensitive_reasons:
        notes.extend([f"manual review: {reason}" for reason in sensitive_reasons])
        return QAResult(False, "needs_manual_review", notes, article)
    if notes:
        return QAResult(False, "failed", notes, article)
    return QAResult(True, "passed", [], article)


def detect_copied_passages(generated_text: str, source_text: str, min_words: int = 12) -> list[str]:
    if not source_text:
        return []
    generated_norm = _normalize(generated_text)
    source_words = _normalize(source_text).split()
    matches: list[str] = []
    for index in range(0, max(0, len(source_words) - min_words + 1)):
        phrase = " ".join(source_words[index : index + min_words])
        if phrase and phrase in generated_norm:
            matches.append(phrase)
            if len(matches) >= 3:
                break
    return matches


def detects_hallucinated_citations(text: str) -> bool:
    citation_like = re.findall(r"\((?:[A-Z][A-Za-z-]+(?: and [A-Z][A-Za-z-]+)?|[A-Z][A-Za-z-]+ et al\.)\s+\d{4}[a-z]?\)", text)
    return bool(citation_like)


def sensitive_topic_reasons(article: GeneratedArticle, generated_text: str) -> list[str]:
    reasons = list(article.sensitive_topic_reasons if article.sensitive_topic else [])
    lowered = generated_text.lower()
    for pattern in SENSITIVE_PATTERNS:
        if re.search(pattern, lowered):
            reasons.append(f"matched pattern {pattern}")
    return sorted(set(reasons))


def _combined_generated_text(article: GeneratedArticle) -> str:
    chunks = [article.title, article.attribution]
    for level in [article.elementary, article.middle, article.high_school]:
        chunks.extend(
            [
                level.summary,
                " ".join(level.key_ideas),
                " ".join(f"{term.term} {term.definition}" for term in level.important_terms),
                level.example,
                level.why_it_matters,
                " ".join(level.questions_to_think_about),
            ]
        )
    return "\n".join(chunks)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s-]", " ", text.lower())).strip()
