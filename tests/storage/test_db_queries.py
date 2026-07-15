from phil_encyclopedia.storage.db import Repository, _strip_nul


def test_repository_exposes_completed_summary_slugs_query():
    assert hasattr(Repository, "completed_summary_slugs")


def test_strip_nul_recursively_removes_postgres_invalid_bytes():
    value = {
        "summary": "hello\x00 world",
        "items": ["a\x00", {"term": "b\x00"}],
    }

    assert _strip_nul(value) == {
        "summary": "hello world",
        "items": ["a", {"term": "b"}],
    }
