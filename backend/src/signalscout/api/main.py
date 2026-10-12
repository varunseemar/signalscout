import csv
from contextlib import asynccontextmanager
import io
import threading
import time
from collections import defaultdict, deque
from datetime import date, timedelta
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from signalscout.config import get_settings
from signalscout.db import (
    Article,
    Company,
    FundingEvent,
    IcpProfile,
    PipelineRun,
    SessionLocal,
    SpiderHealth,
    init_db,
    session_scope,
)
from signalscout.pipeline.extract import ROUNDS, SECTORS
from signalscout.pipeline.llm import LLMUnavailable
from signalscout.pipeline.orchestrator import get_icp, rescore_all, run_pipeline

@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    # Runs execute in a background thread of this process; if the process restarted
    # mid-run, that thread is gone. Close them out so the UI doesn't spin forever.
    with session_scope() as s:
        for run in s.scalars(select(PipelineRun).where(PipelineRun.status == "running")):
            run.status, run.stage, run.error = "failed", None, "Interrupted: API restarted during the run"
            run.finished_at = func.now()
    yield


app = FastAPI(lifespan=lifespan, title="SignalScout API", version="0.1.0",
              description="Funding-signal lead engine: who to contact today, and why.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().cors_origins.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


Status = Literal["new", "shortlisted", "contacted", "dismissed"]


# ---------- public demo protection ----------

def is_admin(x_admin_token: str | None = Header(None)) -> bool:
    token = get_settings().admin_token
    return not token or x_admin_token == token


def require_admin(admin: bool = Depends(is_admin)) -> None:
    if not admin:
        raise HTTPException(403, "This is a read-only demo. Running the pipeline, editing leads and "
                                 "changing the ICP need the admin key.")


_draft_log: dict[str, deque] = defaultdict(deque)


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "unknown")


def _draft_allowed(ip: str) -> bool:
    window, log = 3600, _draft_log[ip]
    now = time.monotonic()
    while log and now - log[0] > window:
        log.popleft()
    if len(log) >= get_settings().email_drafts_per_hour:
        return False
    log.append(now)
    return True


@app.get("/api/config")
def client_config(admin: bool = Depends(is_admin)):
    return {"read_only": bool(get_settings().admin_token), "is_admin": admin}


# ---------- serialisation ----------

def event_dict(e: FundingEvent) -> dict:
    return {
        "id": e.id, "round_type": e.round_type, "amount_usd": e.amount_usd, "valuation_usd": e.valuation_usd,
        "investors": e.investors, "lead_investors": e.lead_investors, "use_of_funds": e.use_of_funds,
        "summary": e.summary, "announced_on": e.announced_on, "source_count": len(e.article_ids),
    }


def lead_dict(c: Company, detail: bool = False) -> dict:
    latest = c.funding_events[0] if c.funding_events else None
    d = {
        "id": c.id, "name": c.name, "domain": c.domain, "website": c.website, "description": c.description,
        "sector": c.sector, "hq_city": c.hq_city, "hq_country": c.hq_country, "score": c.score,
        "score_breakdown": c.score_breakdown, "score_reasons": c.score_reasons, "data_quality": c.data_quality,
        "status": c.status, "hiring": c.hiring, "enrich_status": c.enrich_status,
        "best_email": c.emails[0] if c.emails else None, "email_count": len(c.emails),
        "phone": c.phones[0]["display"] if c.phones else None, "linkedin": c.socials.get("linkedin"),
        "latest_round": event_dict(latest) if latest else None,
    }
    if detail:
        d.update({
            "emails": c.emails, "phones": c.phones, "socials": c.socials, "people": c.people,
            "website_source": c.website_source, "site_title": c.site_title,
            "meta_description": c.meta_description, "notes": c.notes, "email_draft": c.email_draft,
            "enriched_at": c.enriched_at, "funding_events": [event_dict(e) for e in c.funding_events],
        })
    return d


# ---------- leads ----------

def _lead_query(q, sector, stage, status, min_score, days, has_email):
    stmt = select(Company).options(selectinload(Company.funding_events))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Company.name.ilike(like), Company.description.ilike(like), Company.domain.ilike(like)))
    if sector:
        stmt = stmt.where(Company.sector.in_(sector))
    if status:
        stmt = stmt.where(Company.status.in_(status))
    else:
        stmt = stmt.where(Company.status != "dismissed")
    if min_score:
        stmt = stmt.where(Company.score >= min_score)
    if stage or days:
        sub = select(FundingEvent.company_id)
        if stage:
            sub = sub.where(FundingEvent.round_type.in_(stage))
        if days:
            sub = sub.where(FundingEvent.announced_on >= date.today() - timedelta(days=days))
        stmt = stmt.where(Company.id.in_(sub))
    if has_email:
        stmt = stmt.where(func.jsonb_array_length(Company.emails) > 0)
    return stmt


@app.get("/api/leads")
def list_leads(
    q: str | None = None,
    sector: list[str] | None = Query(None),
    stage: list[str] | None = Query(None),
    status: list[Status] | None = Query(None),
    min_score: int = 0,
    days: int | None = None,
    has_email: bool = False,
    sort: Literal["score", "recent", "amount", "name"] = "score",
    limit: int = Query(100, le=500),
):
    with SessionLocal() as s:
        leads = [lead_dict(c) for c in s.scalars(_lead_query(q, sector, stage, status, min_score, days, has_email))]
    keys = {
        "score": lambda l: -l["score"],
        "recent": lambda l: -(l["latest_round"]["announced_on"].toordinal() if l["latest_round"] and l["latest_round"]["announced_on"] else 0),
        "amount": lambda l: -((l["latest_round"] or {}).get("amount_usd") or 0),
        "name": lambda l: l["name"].lower(),
    }
    leads.sort(key=keys[sort])
    return {"total": len(leads), "items": leads[:limit]}


@app.get("/api/leads/{lead_id}")
def get_lead(lead_id: int):
    with SessionLocal() as s:
        c = s.get(Company, lead_id, options=[selectinload(Company.funding_events)])
        if not c:
            raise HTTPException(404, "Lead not found")
        d = lead_dict(c, detail=True)
        ids = [i for e in c.funding_events for i in e.article_ids]
        d["articles"] = [
            {"id": a.id, "title": a.title, "url": a.url, "source": a.source, "published_at": a.published_at}
            for a in s.scalars(select(Article).where(Article.id.in_(ids)).order_by(Article.published_at.desc()))
        ]
        return d


class LeadPatch(BaseModel):
    status: Status | None = None
    notes: str | None = None


@app.patch("/api/leads/{lead_id}", dependencies=[Depends(require_admin)])
def update_lead(lead_id: int, patch: LeadPatch):
    with session_scope() as s:
        c = s.get(Company, lead_id)
        if not c:
            raise HTTPException(404, "Lead not found")
        for k, v in patch.model_dump(exclude_none=True).items():
            setattr(c, k, v)
    return {"ok": True}


@app.post("/api/leads/{lead_id}/email-draft")
def email_draft(lead_id: int, request: Request, regenerate: bool = False, admin: bool = Depends(is_admin)):
    from signalscout.pipeline.outreach import draft_email

    with session_scope() as s:
        c = s.get(Company, lead_id, options=[selectinload(Company.funding_events)])
        if not c:
            raise HTTPException(404, "Lead not found")
        if c.email_draft and not regenerate:
            return c.email_draft  # cached: no repeat LLM spend
        if not admin and not _draft_allowed(_client_ip(request)):
            raise HTTPException(429, f"Demo limit: {get_settings().email_drafts_per_hour} AI drafts per hour.")
        try:
            draft = draft_email(c, c.funding_events[0] if c.funding_events else None, get_icp(s)["pitch"])
        except LLMUnavailable as e:
            raise HTTPException(503, str(e))
        c.email_draft = draft.model_dump()
        return c.email_draft


# ---------- export ----------

@app.get("/api/export.csv")
def export_csv(
    q: str | None = None,
    sector: list[str] | None = Query(None),
    stage: list[str] | None = Query(None),
    status: list[Status] | None = Query(None),
    min_score: int = 0,
    days: int | None = None,
    has_email: bool = False,
    ids: list[int] | None = Query(None),
):
    """CRM-ready CSV (column names map 1:1 onto HubSpot/Salesforce company + contact import)."""
    with SessionLocal() as s:
        stmt = _lead_query(q, sector, stage, status, min_score, days, has_email)
        if ids:
            stmt = stmt.where(Company.id.in_(ids))
        rows = sorted(s.scalars(stmt), key=lambda c: -c.score)

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Company Name", "Website", "Industry", "City", "Country", "Lead Score", "Data Quality",
                "Last Round", "Amount (USD)", "Announced", "Lead Investors", "Use of Funds",
                "Primary Email", "Email Confidence", "Phone", "LinkedIn", "Key People", "Why Now", "Status"])
    for c in rows:
        e = c.funding_events[0] if c.funding_events else None
        em = c.emails[0] if c.emails else {}
        w.writerow([
            c.name, c.website or "", c.sector or "", c.hq_city or "", c.hq_country or "", c.score, c.data_quality,
            e.round_type if e else "", int(e.amount_usd) if e and e.amount_usd else "",
            e.announced_on if e else "", "; ".join(e.lead_investors) if e else "",
            e.use_of_funds or "" if e else "", em.get("email", ""), em.get("confidence", ""),
            c.phones[0]["e164"] if c.phones else "", c.socials.get("linkedin", ""),
            "; ".join(f"{p['name']} ({p.get('title') or ''})" for p in c.people),
            " | ".join(c.score_reasons), c.status,
        ])
    buf.seek(0)
    filename = f"signalscout-leads-{date.today()}.csv"
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})


# ---------- ICP ----------

class Icp(BaseModel):
    pitch: str
    sectors: list[str]
    countries: list[str]
    stages: list[str]
    min_amount_usd: float
    max_amount_usd: float
    max_age_days: int = 45


@app.get("/api/icp")
def read_icp():
    with session_scope() as s:
        return {"icp": get_icp(s), "options": {"sectors": SECTORS, "stages": ROUNDS}}


@app.put("/api/icp", dependencies=[Depends(require_admin)])
def write_icp(icp: Icp):
    with session_scope() as s:
        row = s.get(IcpProfile, 1) or IcpProfile(id=1)
        row.config = icp.model_dump()
        s.add(row)
    return rescore_all()


# ---------- pipeline + health ----------

_run_lock = threading.Lock()


@app.post("/api/pipeline/run", status_code=202, dependencies=[Depends(require_admin)])
def trigger_run():
    if not _run_lock.acquire(blocking=False):
        raise HTTPException(409, "A pipeline run is already in progress")
    with session_scope() as s:
        run = PipelineRun(status="running", stage="queued", stats={})
        s.add(run)
        s.flush()
        run_id = run.id

    def work():
        try:
            run_pipeline(run_id)
        finally:
            _run_lock.release()

    threading.Thread(target=work, daemon=True).start()
    return {"run_id": run_id}


@app.get("/api/pipeline/runs")
def list_runs(limit: int = 10):
    with SessionLocal() as s:
        runs = s.scalars(select(PipelineRun).order_by(PipelineRun.id.desc()).limit(limit))
        return [{"id": r.id, "status": r.status, "stage": r.stage, "started_at": r.started_at,
                 "finished_at": r.finished_at, "stats": r.stats, "error": r.error} for r in runs]


@app.get("/api/health/sources")
def source_health():
    with SessionLocal() as s:
        latest = (select(SpiderHealth.source, func.max(SpiderHealth.id).label("id"))
                  .group_by(SpiderHealth.source).subquery())
        rows = s.scalars(select(SpiderHealth).join(latest, SpiderHealth.id == latest.c.id))
        return [{"source": r.source, "status": r.status, "message": r.message, "feed_entries": r.feed_entries,
                 "items_new": r.items_new, "items_skipped_seen": r.items_skipped_seen,
                 "items_dropped": r.items_dropped, "checked_at": r.created_at} for r in rows]


@app.get("/api/stats")
def stats():
    with SessionLocal() as s:
        week = date.today() - timedelta(days=7)
        return {
            "articles": s.scalar(select(func.count(Article.id))),
            "funding_articles": s.scalar(select(func.count(Article.id)).where(Article.is_funding.is_(True))),
            "filtered_out": s.scalar(select(func.count(Article.id)).where(Article.is_funding.is_(False))),
            "leads": s.scalar(select(func.count(Company.id)).where(Company.status != "dismissed")),
            "hot_leads": s.scalar(select(func.count(Company.id)).where(Company.score >= 80, Company.status != "dismissed")),
            "with_verified_email": s.scalar(select(func.count(Company.id)).where(
                Company.emails.op("@>")([{"confidence": "high"}]))),
            "raised_this_week_usd": s.scalar(select(func.coalesce(func.sum(FundingEvent.amount_usd), 0))
                                             .where(FundingEvent.announced_on >= week)),
            "merged_duplicates": s.scalar(select(func.coalesce(func.sum(func.jsonb_array_length(FundingEvent.article_ids) - 1), 0))),
        }
