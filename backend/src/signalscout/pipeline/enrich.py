"""
Website enrichment. For each company, politely crawl a few pages of its own site
(home + contact/about/team/careers) and pull out contact channels and signals.

- respects robots.txt, async with bounded concurrency, short timeouts
- results cached per company for ENRICH_TTL_DAYS
- if the article gave no website, try likely domains and accept one only when the
  page title matches the company name (avoids attaching the wrong site)
"""

import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
from parsel import Selector
from pydantic import BaseModel

from signalscout.config import get_settings
from signalscout.pipeline.resolve import name_key, registered_domain
from signalscout.pipeline.validate import EMAIL_RE, clean_emails, clean_phones

log = logging.getLogger(__name__)

_SUBPAGE_HINT = re.compile(r"contact|about|team|company|careers|jobs|leadership|people", re.I)
_HIRING_HINT = re.compile(r"careers|jobs|we.?re hiring|join (our|the) team|open (roles|positions)", re.I)
_SOCIALS = {
    "linkedin": re.compile(r"linkedin\.com/company/[^/?#\"']+", re.I),
    "twitter": re.compile(r"(?:twitter|x)\.com/(?!intent|share|home)[A-Za-z0-9_]{2,15}\b", re.I),
    "github": re.compile(r"github\.com/[A-Za-z0-9-]+", re.I),
    "crunchbase": re.compile(r"crunchbase\.com/organization/[^/?#\"']+", re.I),
}


class SiteCrawler:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self.robots: dict[str, RobotFileParser] = {}

    async def allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        root = f"{parsed.scheme}://{parsed.netloc}"
        if root not in self.robots:
            rp = RobotFileParser()
            try:
                r = await self.client.get(root + "/robots.txt")
                rp.parse(r.text.splitlines() if r.status_code == 200 else [])
            except httpx.HTTPError:
                rp.parse([])
            self.robots[root] = rp
        return self.robots[root].can_fetch(get_settings().user_agent, url)

    async def fetch(self, url: str) -> httpx.Response | None:
        try:
            if not await self.allowed(url):
                return None
            r = await self.client.get(url)
            if r.status_code == 200 and "html" in r.headers.get("content-type", ""):
                return r
        except Exception as e:  # malformed URLs, TLS, decoding: skip the page, not the company
            log.debug("fetch failed %s: %s", url, e)
        return None


_STOP = {
    "with", "that", "their", "from", "into", "this", "they", "your", "which", "using", "help", "helps",
    "company", "platform", "startup", "provides", "builds", "develops", "based", "solutions", "services",
    "technology", "software", "through", "across", "while", "other", "more", "than", "teams", "businesses",
}


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{4,}", text.lower()) if w not in _STOP}


def _site_evidence(name: str, description: str | None, html: str) -> tuple[bool, int, str]:
    """
    (name_in_title, topic_overlap, page_summary) for a candidate homepage.
    topic_overlap counts words shared with the article's description of the company,
    excluding the company's own name (which trivially matches any same-named site).
    """
    sel = Selector(text=html)
    title = (sel.css("title::text").get() or "").strip()
    name_in_title = bool(re.search(rf"(?<![a-z0-9]){re.escape(name.lower())}(?![a-z0-9])", title.lower()))
    page = " ".join([
        title,
        sel.css('meta[name="description"]::attr(content), meta[property="og:description"]::attr(content)').get() or "",
        " ".join(sel.css("h1 ::text, h2 ::text").getall()[:12]),
    ])
    overlap = _words(description or "") & _words(page) - _words(name)
    return name_in_title, len(overlap), re.sub(r"\s+", " ", page)[:600]


def _site_matches(name: str, description: str | None, html: str) -> bool:
    """Strict, offline rule: name in title and >= 2 topic words in common."""
    in_title, overlap, _ = _site_evidence(name, description, html)
    return in_title and overlap >= 2


async def _guess_website(crawler: SiteCrawler, name: str, description: str | None) -> str | None:
    """
    Try name.com/.ai/.io/.co. Strong evidence is accepted directly; borderline candidates
    (name matches but the homepage copy is generic) get a yes/no check from the LLM.
    Short or generic names ("Wally", "Relay", "Atomic") otherwise attach unrelated sites.
    """
    slug = name_key(name)
    if len(slug) < 4 or not description:
        return None
    for tld in ("com", "ai", "io", "co"):
        r = await crawler.fetch(f"https://{slug}.{tld}")
        if not r:
            continue
        in_title, overlap, summary = _site_evidence(name, description, r.text)
        if not in_title:
            continue
        if overlap >= 2:
            return str(r.url)
        # Login walls and parked domains ("Welcome back", "snag.com") give nothing to judge
        if len(_words(summary) - _words(name)) >= 4 and await asyncio.to_thread(
            _llm_confirms, name, description, str(r.url), summary
        ):
            return str(r.url)
    return None


def _llm_confirms(name: str, description: str, url: str, page_summary: str) -> bool:
    from signalscout.pipeline.llm import LLMUnavailable, generate_json

    class Verdict(BaseModel):
        same_company: bool

    prompt = (
        f"News says: '{name}' - {description}\n\nCandidate website {url} shows:\n{page_summary}\n\n"
        "Is this website the official site of that same company? Unrelated businesses that share "
        "the name, parked/for-sale domains and blocked pages are NOT a match. If the page does not "
        "say enough to be confident, answer false."
    )
    try:
        return generate_json(prompt, Verdict).same_company
    except LLMUnavailable:
        return False
    except Exception as e:
        log.warning("site verification failed for %s: %s", name, e)
        return False


async def enrich_one(crawler: SiteCrawler, company) -> dict:
    website = company.website
    if website and not website.startswith(("http://", "https://")):
        website = "https://" + website.lstrip("/")
    website_source = "article"
    if not website:
        website = await _guess_website(crawler, company.name, company.description)
        website_source = "guessed"
    if not website:
        return {"enrich_status": "no_website"}

    home = await crawler.fetch(website)
    if not home:
        return {"enrich_status": "unreachable", "website": website}

    domain = registered_domain(str(home.url))
    pages = [home]
    sel = Selector(text=home.text)
    subpages = []
    for href in sel.css("a::attr(href)").getall():
        if "@" in href or href.startswith(("mailto:", "tel:", "javascript:")):
            continue
        abs_url = urljoin(str(home.url), href)
        if registered_domain(abs_url) == domain and _SUBPAGE_HINT.search(urlparse(abs_url).path):
            if abs_url.split("#")[0] not in subpages:
                subpages.append(abs_url.split("#")[0])
    results = await asyncio.gather(*(crawler.fetch(u) for u in subpages[:4]))
    pages += [r for r in results if r]

    emails, phones, socials = set(), set(), {}
    hiring = False
    for page in pages:
        html = page.text
        psel = Selector(text=html)
        emails |= {m.replace("mailto:", "").split("?")[0] for m in psel.css('a[href^="mailto:"]::attr(href)').getall()}
        emails |= set(EMAIL_RE.findall(" ".join(psel.css("body ::text").getall())))
        phones |= {t.replace("tel:", "") for t in psel.css('a[href^="tel:"]::attr(href)').getall()}
        for key, rx in _SOCIALS.items():
            if key not in socials and (m := rx.search(html)):
                socials[key] = "https://" + m.group(0).rstrip("/")
        hiring = hiring or bool(_HIRING_HINT.search(str(page.url))) or bool(
            psel.css('a[href*="careers"], a[href*="jobs"], a[href*="greenhouse.io"], a[href*="lever.co"]')
        )

    return {
        "enrich_status": "ok",
        "website": str(home.url),
        "website_source": website_source,
        "domain": domain,
        "site_title": (sel.css("title::text").get() or "").strip()[:200] or None,
        "meta_description": sel.css('meta[name="description"]::attr(content)').get(),
        "emails": clean_emails(emails, domain),
        "phones": clean_phones(phones, company.hq_country),
        "socials": socials,
        "hiring": hiring,
        "pages_crawled": len(pages),
    }


def needs_enrichment(company) -> bool:
    if company.enriched_at is None:
        return True
    ttl = timedelta(days=get_settings().enrich_ttl_days)
    return datetime.now(timezone.utc) - company.enriched_at > ttl


async def enrich_many(companies: list) -> dict[int, dict]:
    settings = get_settings()
    sem = asyncio.Semaphore(settings.enrich_concurrency)
    async with httpx.AsyncClient(
        timeout=settings.http_timeout,
        follow_redirects=True,
        headers={"User-Agent": settings.user_agent},
        limits=httpx.Limits(max_connections=settings.enrich_concurrency * 2),
    ) as client:
        crawler = SiteCrawler(client)

        async def run(c):
            async with sem:
                try:
                    return c.id, await enrich_one(crawler, c)
                except Exception as e:  # one bad site must never sink the batch
                    log.warning("enrich failed for %s: %s", c.name, e)
                    return c.id, {"enrich_status": "error"}

        return dict(await asyncio.gather(*(run(c) for c in companies)))
