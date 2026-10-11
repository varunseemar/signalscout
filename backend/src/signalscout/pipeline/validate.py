"""Contact validation: email syntax + MX, role/personal classification, phone normalisation."""

import re
from functools import lru_cache

import dns.exception
import dns.resolver
import phonenumbers

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,24}\b")
_ASSET_EXT = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".css", ".js")
_ROLE_PREFIXES = {
    "info", "hello", "contact", "sales", "support", "help", "team", "press", "media", "pr", "admin",
    "office", "careers", "jobs", "hr", "partners", "partnerships", "marketing", "privacy", "legal",
    "security", "billing", "investors", "ir", "hi", "general", "enquiries", "inquiries", "feedback",
}
_JUNK = ("example.com", "sentry.io", "wixpress.com", "domain.com", "email.com", "yourcompany", "sentry-next")
_COUNTRY_REGION = {"united states": "US", "canada": "CA", "united kingdom": "GB", "india": "IN",
                   "germany": "DE", "france": "FR", "israel": "IL", "australia": "AU", "singapore": "SG"}


@lru_cache(maxsize=2048)
def has_mx(domain: str) -> bool:
    try:
        dns.resolver.resolve(domain, "MX", lifetime=4)
        return True
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers):
        return False
    except dns.exception.Timeout:
        return False


def clean_emails(raw: set[str], company_domain: str | None) -> list[dict]:
    """
    Keep plausible emails and annotate them. Confidence:
      high   - on the company's own domain and the domain accepts mail (MX)
      medium - MX ok but different domain (e.g. a gmail founder address)
      low    - no MX record: likely to bounce
    """
    out: dict[str, dict] = {}
    for e in raw:
        e = e.strip().strip(".").lower()
        e = re.sub(r"^(u00[0-9a-f]{2}|x[0-9a-f]{2})+", "", e)  # JSON/JS-escaped chars glued on, e.g. "u003e"
        if e.endswith(_ASSET_EXT) or any(j in e for j in _JUNK) or len(e) > 80:
            continue
        local, _, domain = e.partition("@")
        if not local or not domain:
            continue
        mx = has_mx(domain)
        same_domain = bool(company_domain) and (domain == company_domain or domain.endswith("." + company_domain))
        confidence = "high" if mx and same_domain else "medium" if mx else "low"
        out[e] = {
            "email": e,
            "type": "role" if local.split(".")[0] in _ROLE_PREFIXES else "personal",
            "mx_valid": mx,
            "same_domain": same_domain,
            "confidence": confidence,
        }
    rank = {"high": 0, "medium": 1, "low": 2}
    return sorted(out.values(), key=lambda x: (rank[x["confidence"]], x["type"] != "personal"))[:10]


def clean_phones(raw: set[str], country: str | None) -> list[dict]:
    region = _COUNTRY_REGION.get((country or "").lower(), "US")
    out: dict[str, dict] = {}
    for p in raw:
        try:
            num = phonenumbers.parse(p, region)
        except phonenumbers.NumberParseException:
            continue
        if not phonenumbers.is_valid_number(num):
            continue
        e164 = phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)
        out[e164] = {
            "e164": e164,
            "display": phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.INTERNATIONAL),
            "region": phonenumbers.region_code_for_number(num),
        }
    return list(out.values())[:5]


def data_quality(company) -> int:
    """0-100: how complete and trustworthy the contact record is."""
    score = 0
    if company.domain:
        score += 20
    if company.enrich_status == "ok":
        score += 15
    if any(e["confidence"] == "high" for e in company.emails):
        score += 25
    elif any(e["mx_valid"] for e in company.emails):
        score += 12
    if company.phones:
        score += 15
    if company.socials.get("linkedin"):
        score += 10
    if company.people:
        score += 15
    return min(score, 100)
