from pathlib import Path

from phil_encyclopedia.config import Settings
from phil_encyclopedia.processing.cost_estimate import estimate_generation_cost, estimate_tokens


def test_estimate_tokens_uses_character_ratio():
    assert estimate_tokens("abcd", chars_per_token=4) == 2


def test_estimate_generation_cost_counts_cached_articles(tmp_path: Path):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True)
    (cache_dir / "test.html").write_text(
        """
        <html><body>
          <h1>Test</h1>
          <main id="article"><p>This is enough source text for a tiny estimate.</p></main>
        </body></html>
        """,
        encoding="utf-8",
    )
    settings = Settings(
        database_url="postgresql://localhost/test",
        openai_api_key=None,
        openai_model="test-model",
        openai_batch_completion_window="24h",
        openai_max_source_chars=220000,
        sep_user_agent="test",
        sep_crawl_delay_seconds=5,
        raw_cache_dir=cache_dir,
        raw_cache_retention_days=7,
        prompt_version="test",
    )

    estimate = estimate_generation_cost(
        ["https://plato.stanford.edu/entries/test/", "https://plato.stanford.edu/entries/missing/"],
        settings,
        output_tokens_per_article=100,
        input_cost_per_million=1,
        output_cost_per_million=2,
    )

    assert estimate.article_count == 1
    assert estimate.missing_cache_count == 1
    assert estimate.output_tokens == 100
    assert estimate.total_cost_usd > 0
