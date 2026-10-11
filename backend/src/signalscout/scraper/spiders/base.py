from datetime import date, datetime, timedelta, timezone
from time import mktime

import feedparser
import scrapy
from parsel import Selector
from sqlalchemy import select

from signalscout.config import get_settings
from signalscout.db import Article, SessionLocal
from signalscout.scraper.text import first_html, first_text, html_to_text, outbound_links, url_hash


class FeedSpider(scrapy.Spider):
    """
    Base spider: read an RSS feed, skip anything already stored, then build an article
    either from the feed's full-text <content:encoded> or by fetching the article page.

    Subclasses set `feed_urls` and, if the feed has no full text, `body_css` (fallback list).
    Pass `-a debug_url=<article url>` to parse a single article page for selector debugging.
    """

    feed_urls: list[str] = []
    full_text_in_feed = False
    title_css: tuple[str, ...] = ("h1 ::text",)
    body_css: tuple[str, ...] = ("article",)
    author_css: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()  # optional title pre-filter for general-news feeds

    def __init__(self, *args, debug_url: str | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.debug_url = debug_url
        self.lookback = date.today() - timedelta(days=get_settings().feed_lookback_days)

    async def start(self):
        if self.debug_url:
            yield scrapy.Request(self.debug_url, callback=self.parse_article, cb_kwargs={"entry": {}})
            return
        self.seen = self._load_seen_hashes()
        for url in self.feed_urls:
            yield scrapy.Request(url, callback=self.parse_feed)

    def _load_seen_hashes(self) -> set[str]:
        # DB-backed equivalent of DeltaFetch: never re-download an article we already stored.
        with SessionLocal() as s:
            return set(s.scalars(select(Article.url_hash).where(Article.source == self.name)))

    def parse_feed(self, response):
        feed = feedparser.parse(response.body)
        self.crawler.stats.inc_value("feed/entries", len(feed.entries))
        for entry in feed.entries:
            link = entry.get("link")
            if not link:
                continue
            published = _entry_date(entry)
            if published and published < self.lookback:
                self.crawler.stats.inc_value("feed/too_old")
                continue
            if self.keywords and not any(k in entry.get("title", "").lower() for k in self.keywords):
                self.crawler.stats.inc_value("feed/filtered_keyword")
                continue
            h = url_hash(link)
            if h in self.seen:
                self.crawler.stats.inc_value("feed/skipped_seen")
                continue
            self.seen.add(h)

            meta = {"link": link, "title": entry.get("title"), "author": entry.get("author"),
                    "published": published}
            if self.full_text_in_feed and entry.get("content"):
                html = entry["content"][0].get("value", "")
                yield self.build_item(meta, html)
            else:
                yield scrapy.Request(link, callback=self.parse_article, cb_kwargs={"entry": meta})

    def parse_article(self, response, entry: dict):
        sel = Selector(text=response.text)
        body = first_html(sel, *self.body_css) or ""
        meta = {
            "link": response.url,
            "title": first_text(sel, *self.title_css) or entry.get("title"),
            "author": (first_text(sel, *self.author_css) if self.author_css else None) or entry.get("author"),
            "published": entry.get("published") or _page_date(sel),
        }
        yield self.build_item(meta, body)

    def build_item(self, meta: dict, body_html: str) -> dict:
        return {
            "url": meta["link"],
            "url_hash": url_hash(meta["link"]),
            "source": self.name,
            "title": (meta.get("title") or "").strip(),
            "author": meta.get("author"),
            "published_at": meta.get("published"),
            "text": html_to_text(body_html),
            "outbound_links": outbound_links(body_html, meta["link"]),
        }


def _entry_date(entry) -> date | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    return datetime.fromtimestamp(mktime(parsed), tz=timezone.utc).date()


def _page_date(sel: Selector) -> date | None:
    raw = sel.css('meta[property="article:published_time"]::attr(content), time::attr(datetime)').get()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        return None
