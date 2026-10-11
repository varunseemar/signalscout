"""
Export the processed dataset to /data for the repo.

Full article text is deliberately left out (it is the publishers' copyrighted content);
the article index keeps title, URL, source, date and how the pipeline classified it.
"""

import csv
import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from signalscout.config import BACKEND_DIR
from signalscout.db import Article, Company, SessionLocal

DATA_DIR = BACKEND_DIR.parent / "data"


def export_dataset(out: Path = DATA_DIR) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    with SessionLocal() as s:
        articles = list(s.scalars(select(Article).order_by(Article.published_at.desc(), Article.id)))
        companies = list(s.scalars(
            select(Company).options(selectinload(Company.funding_events)).order_by(Company.score.desc(), Company.name)
        ))

    with open(out / "articles_index.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "source", "published_at", "title", "url", "is_company_funding", "skip_reason"])
        for a in articles:
            w.writerow([a.id, a.source, a.published_at, a.title, a.url, a.is_funding, a.skip_reason or ""])

    leads = []
    for c in companies:
        leads.append({
            "id": c.id, "name": c.name, "domain": c.domain, "website": c.website, "website_source": c.website_source,
            "description": c.description, "sector": c.sector, "hq_city": c.hq_city, "hq_country": c.hq_country,
            "score": c.score, "score_breakdown": c.score_breakdown, "score_reasons": c.score_reasons,
            "data_quality": c.data_quality, "enrich_status": c.enrich_status, "hiring": c.hiring,
            "emails": c.emails, "phones": c.phones, "socials": c.socials, "people": c.people,
            "funding_events": [
                {
                    "round_type": e.round_type, "amount_usd": e.amount_usd, "valuation_usd": e.valuation_usd,
                    "announced_on": e.announced_on.isoformat() if e.announced_on else None,
                    "lead_investors": e.lead_investors, "investors": e.investors,
                    "use_of_funds": e.use_of_funds, "summary": e.summary, "source_article_ids": e.article_ids,
                }
                for e in c.funding_events
            ],
        })
    (out / "leads.json").write_text(json.dumps(leads, indent=2, ensure_ascii=False), encoding="utf-8")

    with open(out / "leads.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["name", "website", "sector", "city", "country", "score", "data_quality", "round", "amount_usd",
                    "announced_on", "lead_investors", "primary_email", "email_confidence", "phone", "linkedin",
                    "people", "why_now"])
        for l in leads:
            e = l["funding_events"][0] if l["funding_events"] else {}
            em = l["emails"][0] if l["emails"] else {}
            w.writerow([
                l["name"], l["website"] or "", l["sector"] or "", l["hq_city"] or "", l["hq_country"] or "",
                l["score"], l["data_quality"], e.get("round_type", ""),
                int(e["amount_usd"]) if e.get("amount_usd") else "", e.get("announced_on") or "",
                "; ".join(e.get("lead_investors", [])), em.get("email", ""), em.get("confidence", ""),
                l["phones"][0]["e164"] if l["phones"] else "", l["socials"].get("linkedin", ""),
                "; ".join(f"{p['name']} ({p.get('title') or ''})" for p in l["people"]),
                " | ".join(l["score_reasons"]),
            ])

    return {"articles": len(articles), "leads": len(leads), "out": str(out)}
