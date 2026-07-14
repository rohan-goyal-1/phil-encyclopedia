from datetime import date

from phil_encyclopedia.input.parser import parse_sep_article


def test_parse_sep_article_extracts_core_fields():
    html = """
    <html>
      <head><title>Knowledge | Stanford Encyclopedia of Philosophy</title></head>
      <body>
        <h1>Knowledge</h1>
        <div class="authors">By Alice Example and Bob Example</div>
        <div class="pubinfo">First published Mon Jan 1, 2001; substantive revision Tue Feb 2, 2021</div>
        <nav id="toc"><ul><li><a href="#one">Introduction</a></li><li><a href="#bib">Bibliography</a></li></ul></nav>
        <main id="article">
          <p>First published Mon Jan 1, 2001; substantive revision Tue Feb 2, 2021</p>
          <h2>Introduction</h2>
          <p>Knowledge is often discussed with belief and truth.</p>
          <p>See <a href="/entries/epistemology/">Epistemology</a>.</p>
          <h2>Bibliography</h2>
        </main>
      </body>
    </html>
    """
    parsed = parse_sep_article(html, "https://plato.stanford.edu/entries/knowledge/")
    assert parsed.title == "Knowledge"
    assert parsed.authors == ["Alice Example and Bob Example"]
    assert parsed.first_published == date(2001, 1, 1)
    assert parsed.last_revised == date(2021, 2, 2)
    assert "Introduction" in parsed.table_of_contents
    assert parsed.bibliography_marker == "Bibliography"
    assert parsed.related_links[0].slug == "epistemology"
    assert "Knowledge is often discussed" in parsed.main_text
