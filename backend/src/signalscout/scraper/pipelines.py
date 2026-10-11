import hashlib
import os

from pydantic import ValidationError
from scrapy import signals
from scrapy.exceptions import DropItem
from sqlalchemy.dialects.postgresql import insert

from signalscout.db import Article, SessionLocal, SpiderHealth


class _CrawlerAware:
    """Scrapy 2.13+ style: get the crawler via from_crawler instead of per-call spider args."""

    def __init__(self, crawler):
        self.crawler = crawler

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler)

    @property
    def stats(self):
        return self.crawler.stats


class ValidationPipeline(_CrawlerAware):
    """Enforce the ArticleItem contract; a failure usually means a selector broke."""

    def process_item(self, item):
        from signalscout.scraper.items import ArticleItem

        try:
            article = ArticleItem(**item)
        except ValidationError as e:
            for err in e.errors():
                self.stats.inc_value(f"validation/errors/{err['loc'][0]}")
            raise DropItem(f"Invalid item {item.get('url')}: {e.error_count()} errors")
        data = article.model_dump()
        data["url"] = str(data["url"])
        return data


class DupeFilterPipeline(_CrawlerAware):
    """Same story syndicated under two URLs in one run (title + date fingerprint)."""

    def __init__(self, crawler):
        super().__init__(crawler)
        self.seen: dict[bytes, str] = {}

    def process_item(self, item):
        key = hashlib.sha1(f"{item['title'].lower()}|{item['published_at']}".encode()).digest()
        if key in self.seen:
            self.stats.inc_value("dupes/dropped")
            raise DropItem(f"Duplicate of {self.seen[key]}")
        self.seen[key] = item["url"]
        return item


class PostgresPipeline(_CrawlerAware):
    """Idempotent insert keyed on url_hash: re-running a crawl can never create duplicates."""

    def open_spider(self):
        self.session = SessionLocal()

    def close_spider(self):
        self.session.close()

    def process_item(self, item):
        stmt = insert(Article).values(**item).on_conflict_do_nothing(index_elements=["url_hash"])
        result = self.session.execute(stmt)
        self.session.commit()
        self.stats.inc_value("db/inserted" if result.rowcount else "db/conflict")
        return item


class HealthRecorder:
    """Spidermon-lite: persist per-source stats and flag sources that look broken."""

    def __init__(self, crawler):
        self.crawler = crawler

    @classmethod
    def from_crawler(cls, crawler):
        ext = cls(crawler)
        crawler.signals.connect(ext.spider_closed, signal=signals.spider_closed)
        return ext

    def spider_closed(self, spider, reason):
        stats = self.crawler.stats.get_stats()
        entries = stats.get("feed/entries", 0)
        new = stats.get("db/inserted", 0)
        dropped = stats.get("item_dropped_count", 0) - stats.get("dupes/dropped", 0)
        errors = stats.get("log_count/ERROR", 0)
        attempted = new + dropped

        status, message = "ok", None
        if spider.debug_url:
            return
        if entries == 0:
            status, message = "broken", "Feed returned 0 entries - URL or format changed?"
        elif reason != "finished":
            status, message = "broken", f"Spider closed early: {reason}"
        elif attempted and dropped / attempted >= 0.5:
            status, message = "warning", f"{dropped}/{attempted} items failed validation - selectors may be stale"
        elif errors:
            status, message = "warning", f"{errors} errors logged"

        run_id = os.environ.get("SIGNALSCOUT_RUN_ID")
        with SessionLocal() as s:
            s.add(SpiderHealth(
                run_id=int(run_id) if run_id else None,
                source=spider.name,
                feed_entries=entries,
                items_new=new,
                items_skipped_seen=stats.get("feed/skipped_seen", 0),
                items_dropped=dropped,
                errors=errors,
                status=status,
                message=message,
            ))
            s.commit()
