from signalscout.config import get_settings

BOT_NAME = "signalscout"
SPIDER_MODULES = ["signalscout.scraper.spiders.sources"]

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
)
ROBOTSTXT_OBEY = True

# Politeness: a handful of requests per host, auto-throttled to server latency
CONCURRENT_REQUESTS_PER_DOMAIN = 4
DOWNLOAD_DELAY = 0.5
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_TARGET_CONCURRENCY = 2.0
RETRY_TIMES = 2
RETRY_HTTP_CODES = [429, 500, 502, 503, 504, 522, 524, 408]
DOWNLOAD_TIMEOUT = get_settings().http_timeout

# Dev convenience: cache responses for an hour so iterating on selectors is instant
HTTPCACHE_ENABLED = False
HTTPCACHE_EXPIRATION_SECS = 3600

ITEM_PIPELINES = {
    "signalscout.scraper.pipelines.ValidationPipeline": 100,
    "signalscout.scraper.pipelines.DupeFilterPipeline": 200,
    "signalscout.scraper.pipelines.PostgresPipeline": 300,
}
EXTENSIONS = {"signalscout.scraper.pipelines.HealthRecorder": 500}

LOG_LEVEL = "INFO"
FEED_EXPORT_ENCODING = "utf-8"
