from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse, urlunparse

SEP_BASE_URL = "https://plato.stanford.edu/"
SEP_CONTENTS_URL = urljoin(SEP_BASE_URL, "contents.html")


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._current_href: str | None = None
        self._text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        attr_map = dict(attrs)
        href = attr_map.get("href")
        if href:
            self._current_href = href
            self._text_parts = []

    def handle_data(self, data: str) -> None:
        if self._current_href:
            self._text_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._current_href:
            self.links.append((self._current_href, " ".join(self._text_parts).strip()))
            self._current_href = None
            self._text_parts = []


def canonicalize_url(href: str, base_url: str = SEP_CONTENTS_URL) -> str | None:
    absolute = urljoin(base_url, href)
    parsed = urlparse(absolute)
    if parsed.scheme not in {"http", "https"}:
        return None
    if parsed.netloc != "plato.stanford.edu":
        return None
    path = parsed.path
    if not path.startswith("/entries/") or not path.endswith("/"):
        return None
    return urlunparse(("https", parsed.netloc, path, "", "", ""))


def sep_slug(url: str) -> str:
    path = urlparse(url).path.strip("/")
    if not path.startswith("entries/"):
        raise ValueError(f"Not an SEP entry URL: {url}")
    return path.removeprefix("entries/").strip("/")


def discover_entry_urls(contents_html: str, base_url: str = SEP_CONTENTS_URL) -> list[str]:
    parser = _LinkParser()
    parser.feed(contents_html)
    urls: dict[str, None] = {}
    for href, _text in parser.links:
        canonical = canonicalize_url(href, base_url)
        if canonical:
            urls[canonical] = None
    return sorted(urls)
