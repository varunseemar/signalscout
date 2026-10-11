"""
Entity resolution: map an extracted round onto a Company + FundingEvent.

Company dedupe:  registered domain  ->  normalized name  ->  fuzzy name (>= 92)
Event dedupe:    same company, announced within 45 days, same round type or amount within 15%
"""

import re
import unicodedata
from datetime import date, timedelta
from urllib.parse import urlparse

import tldextract
from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.orm import Session

from signalscout.db import Article, Company, FundingEvent
from signalscout.pipeline.extract import Round

_SUFFIXES = re.compile(
    r"\b(inc|incorporated|llc|ltd|limited|corp|corporation|co|company|gmbh|plc|technologies|"
    r"technology|labs|hq|ai|io)\b\.?",
    re.I,
)
_extract = tldextract.TLDExtract(suffix_list_urls=())  # offline: use bundled public suffix list


def _ascii(text: str) -> str:
    # "Santé" -> "sante" (transliterate rather than drop accented letters)
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def name_key(name: str) -> str:
    plain = _ascii(name)
    key = _SUFFIXES.sub(" ", plain)
    return re.sub(r"[^a-z0-9]+", "", key) or re.sub(r"[^a-z0-9]+", "", plain)


def website_from_links(name: str, links: list[str]) -> str | None:
    """The article often links the company's site without saying so; match it by domain label."""
    key = name_key(name)
    if len(key) < 4:
        return None
    for link in links:
        domain = registered_domain(link)
        if domain and (domain.split(".")[0] == key or domain.split(".")[0].startswith(key)):
            return f"https://{domain}"
    return None


def registered_domain(url: str | None) -> str | None:
    if not url:
        return None
    if "://" not in url:
        url = "https://" + url
    host = urlparse(url).netloc.lower()
    parts = _extract(host)
    if not parts.domain or not parts.suffix:
        return None
    return f"{parts.domain}.{parts.suffix}"


def find_company(s: Session, name: str, domain: str | None, r: Round | None = None,
                 announced: date | None = None) -> Company | None:
    if domain:
        hit = s.scalar(select(Company).where(Company.domain == domain))
        if hit:
            return hit
    key = name_key(name)
    hit = s.scalar(select(Company).where(Company.name_key == key))
    if hit:
        return hit
    # Fuzzy fallback limited to same first letter to keep it cheap
    for cand in s.scalars(select(Company).where(Company.name_key.startswith(key[:1]))):
        if fuzz.ratio(key, cand.name_key) >= 92:
            return cand
        # "Wally" vs "Wally Health": a looser name match is accepted only when the
        # funding round also matches, so two different "Wally"s never get merged.
        loose = fuzz.token_set_ratio(_ascii(name), _ascii(cand.name)) >= 90 or (
            min(len(key), len(cand.name_key)) >= 4
            and (key.startswith(cand.name_key) or cand.name_key.startswith(key))
        )
        if loose and r and _matching_event(s, cand, r, announced or date.today()):
            return cand
    return None


def upsert_round(s: Session, r: Round, article: Article) -> tuple[Company, bool, bool]:
    """Returns (company, company_created, event_created)."""
    if not r.website:
        r.website = website_from_links(r.company_name, article.outbound_links or [])
    domain = registered_domain(r.website)
    company = find_company(s, r.company_name, domain, r, article.published_at)
    created = company is None
    if created:
        company = Company(name=r.company_name.strip(), name_key=name_key(r.company_name), emails=[],
                          phones=[], socials={}, people=[], score_breakdown={}, score_reasons=[])
        s.add(company)

    # Fill blanks only; never overwrite good data with nulls from a thinner article
    if domain and not company.domain:
        company.domain = domain
        company.website = r.website if "://" in r.website else f"https://{r.website}"
    for field in ("description", "sector", "hq_city", "hq_country"):
        if not getattr(company, field) and getattr(r, field):
            setattr(company, field, getattr(r, field))
    known = {p["name"].lower() for p in company.people}
    company.people = company.people + [
        {**p.model_dump(), "source": "article"} for p in r.people if p.name.lower() not in known
    ]
    if r.hiring:
        company.hiring = True
    s.flush()

    announced = article.published_at or date.today()
    event = _matching_event(s, company, r, announced)
    event_created = event is None
    if event_created:
        event = FundingEvent(company_id=company.id, announced_on=announced, article_ids=[], investors=[],
                             lead_investors=[])
        s.add(event)
    if article.id not in event.article_ids:
        event.article_ids = event.article_ids + [article.id]
    event.round_type = event.round_type if event.round_type not in (None, "Undisclosed") else r.round_type
    event.amount_usd = event.amount_usd or r.amount_usd
    event.valuation_usd = event.valuation_usd or r.valuation_usd
    event.use_of_funds = event.use_of_funds or r.use_of_funds
    event.summary = event.summary or r.why_now
    event.investors = _merge(event.investors, r.investors + r.lead_investors)
    event.lead_investors = _merge(event.lead_investors, r.lead_investors)
    if announced < event.announced_on:
        event.announced_on = announced
    s.flush()
    return company, created, event_created


def _matching_event(s: Session, company: Company, r: Round, announced: date) -> FundingEvent | None:
    if company.id is None:
        return None
    window = (announced - timedelta(days=45), announced + timedelta(days=45))
    events = s.scalars(
        select(FundingEvent).where(
            FundingEvent.company_id == company.id, FundingEvent.announced_on.between(*window)
        )
    )
    for ev in events:
        if ev.round_type == r.round_type and r.round_type != "Undisclosed":
            return ev
        if ev.amount_usd and r.amount_usd and abs(ev.amount_usd - r.amount_usd) / ev.amount_usd <= 0.15:
            return ev
    return None


def _merge(existing: list[str], new: list[str]) -> list[str]:
    seen = {x.lower() for x in existing}
    out = list(existing)
    for x in new:
        if x and x.lower() not in seen:
            out.append(x)
            seen.add(x.lower())
    return out
