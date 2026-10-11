"""One class per news source. Adding a source is usually ~10 lines."""

from signalscout.scraper.spiders.base import FeedSpider


class TechCrunchSpider(FeedSpider):
    name = "techcrunch"
    feed_urls = ["https://techcrunch.com/tag/funding/feed/", "https://techcrunch.com/category/venture/feed/"]
    title_css = ("h1.wp-block-post-title ::text", "h1.article-hero__title ::text", "h1 ::text")
    body_css = ("div.entry-content", "div.wp-block-post-content", "article")
    author_css = ("a.post-authors-list__author ::text", "a[rel=author] ::text")


class PRNewswireSpider(FeedSpider):
    name = "prnewswire"
    feed_urls = ["https://www.prnewswire.com/rss/financial-services-latest-news/venture-capital-list.rss"]
    title_css = ("h1 ::text",)
    body_css = ("section.release-body", "div.release-body", "article")
    # The VC list also carries fund launches & hires; keep likely company-raise releases only.
    keywords = ("raise", "funding", "series", "seed", "round", "investment", "secures", "closes")


class GeekWireSpider(FeedSpider):
    name = "geekwire"
    feed_urls = ["https://www.geekwire.com/feed/"]
    full_text_in_feed = True
    keywords = ("raise", "funding", "series", "seed", "round", "lands $", "secures", "backed")


class AlleyWatchSpider(FeedSpider):
    name = "alleywatch"
    feed_urls = ["https://www.alleywatch.com/category/funding/feed/"]
    full_text_in_feed = True


ALL_SPIDERS = [TechCrunchSpider, PRNewswireSpider, GeekWireSpider, AlleyWatchSpider]
