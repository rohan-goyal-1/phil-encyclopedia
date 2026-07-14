from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json

import psycopg
from psycopg.rows import dict_row

from phil_encyclopedia.input.parser import ParsedArticle
from phil_encyclopedia.input.sep_urls import sep_slug
from phil_encyclopedia.processing.models import GeneratedArticle, Level


@dataclass
class Repository:
    database_url: str

    def connect(self):
        return psycopg.connect(self.database_url, row_factory=dict_row)

    def upsert_article(
        self,
        sep_url: str,
        parsed: ParsedArticle,
        source_content_hash: str,
        fetched_at: datetime | None = None,
        status: str = "crawled",
    ) -> int:
        fetched_at = fetched_at or datetime.now(timezone.utc)
        slug = sep_slug(sep_url)
        with self.connect() as conn:
            row = conn.execute(
                """
                INSERT INTO articles (
                  sep_slug, sep_url, title, authors, first_published, last_revised,
                  source_fetched_at, source_content_hash, status, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, now())
                ON CONFLICT (sep_slug) DO UPDATE SET
                  sep_url = EXCLUDED.sep_url,
                  title = EXCLUDED.title,
                  authors = EXCLUDED.authors,
                  first_published = EXCLUDED.first_published,
                  last_revised = EXCLUDED.last_revised,
                  source_fetched_at = EXCLUDED.source_fetched_at,
                  source_content_hash = EXCLUDED.source_content_hash,
                  status = EXCLUDED.status,
                  updated_at = now()
                RETURNING id
                """,
                (
                    slug,
                    sep_url,
                    parsed.title,
                    parsed.authors,
                    parsed.first_published,
                    parsed.last_revised,
                    fetched_at,
                    source_content_hash,
                    status,
                ),
            ).fetchone()
            article_id = int(row["id"])
            self.replace_links(conn, article_id, parsed)
            return article_id

    def replace_links(self, conn, article_id: int, parsed: ParsedArticle) -> None:
        conn.execute("DELETE FROM article_links WHERE source_article_id = %s", (article_id,))
        for link in parsed.related_links:
            conn.execute(
                """
                INSERT INTO article_links (source_article_id, target_sep_slug, target_sep_url, link_text)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (source_article_id, target_sep_slug) DO UPDATE SET
                  target_sep_url = EXCLUDED.target_sep_url,
                  link_text = EXCLUDED.link_text
                """,
                (article_id, link.slug, link.url, link.text),
            )

    def insert_generated_article(
        self,
        article_id: int,
        generated: GeneratedArticle,
        model: str,
        prompt_version: str,
        qa_status: str,
        qa_notes: list[str],
    ) -> None:
        generated_at = datetime.now(timezone.utc)
        with self.connect() as conn:
            for level in ("elementary", "middle", "high_school"):
                summary = getattr(generated, level)
                conn.execute(
                    """
                    INSERT INTO article_summaries (
                      article_id, level, summary, key_ideas, important_terms, example,
                      why_it_matters, questions_to_think_about, reading_time_minutes,
                      model, prompt_version, generated_at, qa_status, qa_notes
                    )
                    VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (article_id, level, model, prompt_version) DO UPDATE SET
                      summary = EXCLUDED.summary,
                      key_ideas = EXCLUDED.key_ideas,
                      important_terms = EXCLUDED.important_terms,
                      example = EXCLUDED.example,
                      why_it_matters = EXCLUDED.why_it_matters,
                      questions_to_think_about = EXCLUDED.questions_to_think_about,
                      reading_time_minutes = EXCLUDED.reading_time_minutes,
                      generated_at = EXCLUDED.generated_at,
                      qa_status = EXCLUDED.qa_status,
                      qa_notes = EXCLUDED.qa_notes
                    """,
                    (
                        article_id,
                        level,
                        summary.summary,
                        summary.key_ideas,
                        json.dumps([term.model_dump() for term in summary.important_terms]),
                        summary.example,
                        summary.why_it_matters,
                        summary.questions_to_think_about,
                        summary.reading_time_minutes,
                        model,
                        prompt_version,
                        generated_at,
                        qa_status,
                        qa_notes,
                    ),
                )
            conn.execute(
                "UPDATE articles SET status = %s, updated_at = now() WHERE id = %s",
                ("needs_review" if qa_status == "needs_manual_review" else "generated", article_id),
            )

    def public_export(self) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT
                  a.sep_slug, a.sep_url, a.title, a.authors, a.first_published, a.last_revised,
                  a.source_fetched_at, a.source_content_hash,
                  jsonb_agg(jsonb_build_object(
                    'level', s.level,
                    'summary', s.summary,
                    'key_ideas', s.key_ideas,
                    'important_terms', s.important_terms,
                    'example', s.example,
                    'why_it_matters', s.why_it_matters,
                    'questions_to_think_about', s.questions_to_think_about,
                    'reading_time_minutes', s.reading_time_minutes,
                    'model', s.model,
                    'prompt_version', s.prompt_version,
                    'generated_at', s.generated_at
                  ) ORDER BY s.level) AS summaries
                FROM articles a
                JOIN article_summaries s ON s.article_id = a.id
                WHERE a.status = 'published' AND s.qa_status = 'passed'
                GROUP BY a.id
                ORDER BY a.title
                """
            ).fetchall()
            return [dict(row) for row in rows]

    def completed_summary_slugs(self, model: str, prompt_version: str) -> set[str]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT a.sep_slug
                FROM articles a
                JOIN article_summaries s ON s.article_id = a.id
                WHERE s.model = %s AND s.prompt_version = %s
                GROUP BY a.id, a.sep_slug
                HAVING COUNT(DISTINCT s.level) = 3
                """,
                (model, prompt_version),
            ).fetchall()
            return {str(row["sep_slug"]) for row in rows}
