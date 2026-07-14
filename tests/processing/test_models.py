from pydantic import ValidationError

from phil_encyclopedia.processing.models import GeneratedArticle
from tests.processing.test_qa import valid_payload


def test_generated_article_accepts_sep_url_strings():
    article = GeneratedArticle.model_validate(valid_payload())

    assert article.sep_url == "https://plato.stanford.edu/entries/test/"
    assert article.read_more_url == "https://plato.stanford.edu/entries/test/"


def test_generated_article_rejects_non_sep_urls():
    payload = valid_payload()
    payload["sep_url"] = "https://example.com/entries/test/"

    try:
        GeneratedArticle.model_validate(payload)
    except ValidationError:
        return

    raise AssertionError("Expected non-SEP URL to be rejected")
