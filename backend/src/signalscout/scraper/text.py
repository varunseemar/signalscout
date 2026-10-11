"""HTML -> clean text helpers shared by spiders."""

import hashlib
import re
from urllib.parse import urljoin, urlparse

from parsel import Selector
from w3lib.html import remove_tags, remove_tags_with_content, replace_entities
from w3lib.url import canonicalize_url

_WS = re.compile(r"[ \t\r\f\v]+")
_BLANK_LINES = re.compile(r"\n\s*\n+")

# Links that never point at the funded company's own website
_NOISE_DOMAINS = (
    "twitter.com", "x.com", "facebook.com", "linkedin.com", "instagram.com", "youtube.com",
    "techcrunch.com", "prnewswire.com", "geekwire.com", "alleywatch.com", "crunchbase.com",
    "wp.com", "wordpress.com", "google.com", "apple.com", "bit.ly", "cision.com", "t.co",
    "feedburner.com", "gravatar.com", "pitchbook.com", "bloomberg.com", "reuters.com",
)


def url_hash(url: str) -> str:
    return hashlib.sha1(canonicalize_url(url).encode("utf-8")).hexdigest()


def html_to_text(html: str) -> str:
    html = remove_tags_with_content(html, which_ones=("script", "style", "noscript", "figure", "iframe"))
    html = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</h\d>", "\n", html)
    text = replace_entities(remove_tags(html))
    lines = [_WS.sub(" ", line).strip() for line in text.split("\n")]
    return _BLANK_LINES.sub("\n\n", "\n".join(line for line in lines if line)).strip()


def first_text(sel: Selector, *css_queries: str) -> str | None:
    """Fallback selectors: return the first query that yields text (survives layout changes)."""
    for query in css_queries:
        value = " ".join(t.strip() for t in sel.css(query).getall() if t.strip())
        if value:
            return value
    return None


def first_html(sel: Selector, *css_queries: str) -> str | None:
    for query in css_queries:
        nodes = sel.css(query)
        if nodes:
            return "".join(nodes.getall())
    return None


def outbound_links(html: str, base_url: str) -> list[str]:
    """External links in an article body; the company's own site is usually among them."""
    sel = Selector(text=html or "")
    seen: list[str] = []
    for href in sel.css("a::attr(href)").getall():
        href = urljoin(base_url, href.strip())
        host = urlparse(href).netloc.lower()
        if not href.startswith("http") or not host:
            continue
        if any(host == d or host.endswith("." + d) for d in _NOISE_DOMAINS):
            continue
        if href not in seen:
            seen.append(href)
    return seen[:25]
