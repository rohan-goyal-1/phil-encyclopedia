from phil_encyclopedia.input.parser import ParsedArticle
from phil_encyclopedia.processing.prompt import build_user_prompt


def test_prompt_requests_distinct_age_group_versions():
    article = ParsedArticle(
        title="Test",
        authors=[],
        first_published=None,
        last_revised=None,
        table_of_contents=[],
        bibliography_marker=None,
        related_links=[],
        main_text="Philosophy source text.",
    )

    prompt = build_user_prompt("test", "https://plato.stanford.edu/entries/test/", article)

    assert "three separate age-appropriate versions" in prompt
    assert "elementary: for roughly ages 8-10" in prompt
    assert "middle: for roughly ages 11-13" in prompt
    assert "high_school: for roughly ages 14-18" in prompt


def test_prompt_default_source_budget_is_large():
    article = ParsedArticle(
        title="Long Test",
        authors=[],
        first_published=None,
        last_revised=None,
        table_of_contents=[],
        bibliography_marker=None,
        related_links=[],
        main_text="x" * 150000,
    )

    prompt = build_user_prompt("long-test", "https://plato.stanford.edu/entries/long-test/", article)

    assert "x" * 150000 in prompt
