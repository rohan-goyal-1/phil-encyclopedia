from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from html.parser import HTMLParser
from urllib.parse import urljoin

from .sep_urls import canonicalize_url, sep_slug


@dataclass(frozen=True)
class RelatedLink:
    slug: str
    url: str
    text: str


@dataclass(frozen=True)
class ParsedArticle:
    title: str
    authors: list[str]
    first_published: date | None
    last_revised: date | None
    table_of_contents: list[str]
    bibliography_marker: str | None
    related_links: list[RelatedLink]
    main_text: str


class _ArticleHTMLParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.title_parts: list[str] = []
        self.h1_parts: list[str] = []
        self.authors: list[str] = []
        self.dates: list[str] = []
        self.toc_items: list[str] = []
        self.related_links: list[RelatedLink] = []
        self.main_parts: list[str] = []
        self.bibliography_marker: str | None = None
        self._tag_stack: list[str] = []
        self._capture_title = False
        self._capture_h1 = False
        self._capture_author = False
        self._capture_date = False
        self._capture_toc = False
        self._capture_main = False
        self._capture_heading = False
        self._heading_parts: list[str] = []
        self._active_link: str | None = None
        self._active_link_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        self._tag_stack.append(tag)
        attrs_map = {k.lower(): v or "" for k, v in attrs}
        classes = set(attrs_map.get("class", "").split())
        element_id = attrs_map.get("id", "")

        if tag == "title":
            self._capture_title = True
        if tag == "h1":
            self._capture_h1 = True
        if tag in {"span", "div", "p"} and ({"author", "authors"} & classes):
            self._capture_author = True
        if tag in {"span", "div", "p"} and ({"pubinfo", "date", "dates"} & classes):
            self._capture_date = True
        if element_id in {"toc", "contents"} or "toc" in classes:
            self._capture_toc = True
        if tag == "main" or element_id in {"article", "main-text", "content"} or "entry" in classes:
            self._capture_main = True
        if tag in {"h2", "h3"}:
            self._capture_heading = True
            self._heading_parts = []
        if tag == "a":
            href = attrs_map.get("href")
            if href:
                self._active_link = href
                self._active_link_text = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title":
            self._capture_title = False
        if tag == "h1":
            self._capture_h1 = False
        if self._capture_author and tag in {"span", "div", "p"}:
            self._capture_author = False
        if self._capture_date and tag in {"span", "div", "p"}:
            self._capture_date = False
        if self._capture_toc and tag in {"ul", "nav", "div"}:
            self._capture_toc = False
        if self._capture_main and tag in {"main", "article"}:
            self._capture_main = False
        if self._capture_heading and tag in {"h2", "h3"}:
            heading = _clean(" ".join(self._heading_parts))
            if heading and "bibliograph" in heading.lower() and not self.bibliography_marker:
                self.bibliography_marker = heading
            self._capture_heading = False
            self._heading_parts = []
        if tag == "a" and self._active_link:
            canonical = canonicalize_url(self._active_link, self.base_url)
            text = _clean(" ".join(self._active_link_text))
            if canonical and text and sep_slug(canonical) != sep_slug(self.base_url):
                self.related_links.append(RelatedLink(sep_slug(canonical), canonical, text))
            self._active_link = None
            self._active_link_text = []
        if tag in {"p", "li", "h2", "h3"} and self._capture_main:
            self.main_parts.append("\n")
        if self._tag_stack:
            self._tag_stack.pop()

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if not text:
            return
        if self._capture_title:
            self.title_parts.append(text)
        if self._capture_h1:
            self.h1_parts.append(text)
        if self._capture_author:
            self.authors.append(text)
        if self._capture_date:
            self.dates.append(text)
        if self._capture_toc and self._tag_stack and self._tag_stack[-1] in {"a", "li"}:
            self.toc_items.append(text)
        if self._capture_main:
            self.main_parts.append(text)
        if self._capture_heading:
            self._heading_parts.append(text)
        if self._active_link:
            self._active_link_text.append(text)


def parse_sep_article(html: str, url: str) -> ParsedArticle:
    parser = _ArticleHTMLParser(url)
    parser.feed(html)
    title = _clean(" ".join(parser.h1_parts or parser.title_parts))
    title = re.sub(r"\s*\|\s*Stanford Encyclopedia of Philosophy.*$", "", title)
    main_text = _clean("\n".join(parser.main_parts))
    date_text = " ".join(parser.dates + [main_text[:1000]])
    first_published = _extract_date(date_text, r"First published\s+([^;.\n]+)")
    last_revised = _extract_date(date_text, r"(?:Substantive revision|Last revised)\s+([^;.\n]+)")
    authors = _dedupe([_clean(author).removeprefix("By ").strip() for author in parser.authors if _clean(author)])
    toc = _dedupe([_clean(item) for item in parser.toc_items if _clean(item)])
    related = list({link.slug: link for link in parser.related_links}.values())
    return ParsedArticle(
        title=title,
        authors=authors,
        first_published=first_published,
        last_revised=last_revised,
        table_of_contents=toc,
        bibliography_marker=parser.bibliography_marker,
        related_links=related,
        main_text=main_text,
    )


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _extract_date(text: str, pattern: str) -> date | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return None
    raw = match.group(1).strip()
    raw = raw.replace(",", "")
    parts = raw.split()
    if parts and parts[0].lower().rstrip(".") in {"mon", "monday", "tue", "tues", "tuesday", "wed", "wednesday", "thu", "thur", "thurs", "thursday", "fri", "friday", "sat", "saturday", "sun", "sunday"}:
        parts = parts[1:]
    if len(parts) < 3:
        return None
    month_names = {
        "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
        "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7,
        "july": 7, "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
        "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
    }
    month = month_names.get(parts[0].lower().rstrip("."))
    if not month:
        return None
    try:
        return date(int(parts[2]), month, int(parts[1]))
    except ValueError:
        return None
