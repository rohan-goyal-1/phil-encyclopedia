from __future__ import annotations

from phil_encyclopedia.input.parser import ParsedArticle

from .models import json_schema

SYSTEM_PROMPT = """You create original educational philosophy explanations for young readers.
Use only the supplied SEP-derived source notes. Do not quote long phrases. Do not invent facts,
citations, biographical details, or controversy resolution. Stay neutral, kind, and precise.
Return exactly one JSON object matching the provided schema, with three distinct versions:
elementary, middle, and high_school."""


def build_user_prompt(
    sep_slug: str,
    sep_url: str,
    article: ParsedArticle,
    max_source_chars: int = 220000,
) -> str:
    source_text = article.main_text[:max_source_chars]
    toc = "\n".join(f"- {item}" for item in article.table_of_contents[:40])
    authors = ", ".join(article.authors)
    return f"""Source metadata:
slug: {sep_slug}
url: {sep_url}
title: {article.title}
authors: {authors}
first_published: {article.first_published}
last_revised: {article.last_revised}

Table of contents:
{toc}

Task:
Create three separate age-appropriate versions of the same SEP entry. The versions must be
substantively faithful to the same source, but they must differ in vocabulary, sentence length,
examples, assumed background knowledge, and conceptual detail:
- elementary: for roughly ages 8-10; use concrete language, short sentences, friendly examples,
  and define any abstract term before using it heavily.
- middle: for roughly ages 11-13; introduce more philosophical vocabulary, explain disagreements,
  and keep examples accessible to early adolescents.
- high_school: for roughly ages 14-18; preserve nuance, explain major distinctions and arguments,
  and use accurate philosophical terminology with definitions.

Each version must include:
- a clear summary in original wording
- key ideas
- definitions for important terms
- one age-fitting example
- why it matters
- questions to think about
- a reading time estimate

Rules:
- Do not copy source wording except unavoidable short names or technical terms.
- Do not include long quotations.
- Do not make claims beyond the source.
- Do not merely simplify the same paragraph three times; write each age-group version for its
  intended readers.
- Use neutral framing for disputes and sensitive topics.
- Include read_more_url as the SEP source URL.
- Attribution must begin exactly: Based on the Stanford Encyclopedia of Philosophy entry:
- Mark sensitive_topic true for abortion, race, religion, violence, sexuality, death, political ideology,
  or other topics that need adult/manual review before publication.

JSON schema:
{json_schema()}

Source text for temporary processing:
{source_text}
"""
