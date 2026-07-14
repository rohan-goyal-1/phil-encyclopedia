from phil_encyclopedia.input.sep_urls import discover_entry_urls


def test_discover_entry_urls_filters_and_dedupes():
    html = """
    <a href="entries/aristotle/">Aristotle</a>
    <a href="/entries/logic-classical/">Classical Logic</a>
    <a href="entries/nested/topic/">Nested</a>
    <a href="entries/aristotle/#see-also">Duplicate with fragment</a>
    <a href="archives/win2024/entries/old/">Archive</a>
    <a href="https://example.com/entries/nope/">External</a>
    <a href="contents.html">Contents</a>
    """
    assert discover_entry_urls(html) == [
        "https://plato.stanford.edu/entries/aristotle/",
        "https://plato.stanford.edu/entries/logic-classical/",
        "https://plato.stanford.edu/entries/nested/topic/",
    ]
