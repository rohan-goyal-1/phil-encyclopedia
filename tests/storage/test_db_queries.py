from phil_encyclopedia.storage.db import Repository


def test_repository_exposes_completed_summary_slugs_query():
    assert hasattr(Repository, "completed_summary_slugs")
