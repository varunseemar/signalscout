import asyncio
import logging
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from signalscout.config import get_settings
from signalscout.db import Article, Company, IcpProfile, PipelineRun, session_scope
from signalscout.pipeline.enrich import enrich_many, needs_enrichment
from signalscout.pipeline.extract import extract_rounds, looks_like_funding
from signalscout.pipeline.llm import LLMUnavailable
from signalscout.pipeline.resolve import upsert_round
from signalscout.pipeline.score import DEFAULT_ICP, score_company
from signalscout.pipeline.validate import data_quality

log = logging.getLogger(__name__)


def now() -> datetime:
    return datetime.now(timezone.utc)


def get_icp(s) -> dict:
    row = s.get(IcpProfile, 1)
    if row is None:
        row = IcpProfile(id=1, config=DEFAULT_ICP)
        s.add(row)
        s.flush()
    return {**DEFAULT_ICP, **row.config}


def extract_new(stats: Counter) -> None:
    settings = get_settings()
    with session_scope() as s:
        pending = list(s.scalars(
            select(Article).where(Article.processed_at.is_(None))
            .order_by(Article.published_at.desc().nullslast()).limit(settings.max_extract_per_run * 3)
        ))
        to_llm = []
        for a in pending:
            if looks_like_funding(a.title, a.text):
                to_llm.append((a.id, a.title, a.text, a.url, a.outbound_links))
            else:  # keyword pre-filter: no LLM spend on obvious non-funding news
                a.processed_at, a.is_funding, a.skip_reason = now(), False, "prefilter"
                stats["articles_prefiltered"] += 1
        to_llm = to_llm[: settings.max_extract_per_run]

    def call(job):
        article_id, *args = job
        return article_id, extract_rounds(*args)

    # LLM calls run in parallel; each result is committed as soon as it lands, so progress
    # is visible and a crash mid-run keeps everything already paid for.
    with ThreadPoolExecutor(settings.llm_concurrency) as pool:
        futures = {pool.submit(call, job): job[0] for job in to_llm}
        for fut in as_completed(futures):
            try:
                article_id, extraction = fut.result()
            except LLMUnavailable:
                raise
            except Exception as e:
                log.warning("extraction failed for article %s: %s", futures[fut], e)
                stats["llm_errors"] += 1
                continue  # left unprocessed -> retried next run
            with session_scope() as s:
                article = s.get(Article, article_id)
                article.processed_at = now()
                article.is_funding = bool(extraction.rounds)
                stats["articles_extracted"] += 1
                if not extraction.rounds:
                    article.skip_reason = "not_company_funding"
                    stats["articles_not_funding"] += 1
                for r in extraction.rounds:
                    _, company_new, event_new = upsert_round(s, r, article)
                    stats["companies_new" if company_new else "companies_merged"] += 1
                    stats["events_new" if event_new else "events_merged"] += 1


def enrich_pending(stats: Counter) -> None:
    with session_scope() as s:
        companies = [c for c in s.scalars(select(Company)) if needs_enrichment(c)]
        if not companies:
            return
        results = asyncio.run(enrich_many(companies))
        for c in companies:
            res = results.get(c.id, {"enrich_status": "error"})
            stats[f"enrich_{res['enrich_status']}"] += 1
            domain = res.pop("domain", None)
            res.pop("pages_crawled", None)
            if domain and not c.domain:
                clash = s.scalar(select(Company).where(Company.domain == domain, Company.id != c.id))
                if clash is None:
                    c.domain = domain
            for k, v in res.items():
                if v is not None and hasattr(c, k):
                    setattr(c, k, v)
            if res["enrich_status"] != "error":  # errors retry on the next run
                c.enriched_at = now()


def rescore_all() -> dict:
    with session_scope() as s:
        icp = get_icp(s)
        companies = s.scalars(select(Company).options(selectinload(Company.funding_events)))
        n = 0
        for c in companies:
            c.data_quality = data_quality(c)
            latest = c.funding_events[0] if c.funding_events else None
            c.score, c.score_breakdown, c.score_reasons = score_company(c, latest, icp)
            n += 1
    return {"rescored": n}


def process_new() -> dict:
    stats: Counter = Counter()
    extract_new(stats)
    enrich_pending(stats)
    stats.update(rescore_all())
    return dict(stats)


def run_pipeline(run_id: int | None = None) -> dict:
    from signalscout.cli import crawl_subprocess

    with session_scope() as s:
        run = s.get(PipelineRun, run_id) if run_id else None
        if run is None:
            run = PipelineRun(status="running", stats={})
            s.add(run)
            s.flush()
        run_id = run.id

    def stage(name: str):
        with session_scope() as s:
            s.get(PipelineRun, run_id).stage = name

    stats: Counter = Counter()
    try:
        stage("crawling")
        if crawl_subprocess(run_id) != 0:
            stats["crawl_failed"] += 1
        stage("extracting")
        extract_new(stats)
        stage("enriching")
        enrich_pending(stats)
        stage("scoring")
        stats.update(rescore_all())
        status, error = "finished", None
    except Exception as e:
        log.exception("pipeline failed")
        status, error = "failed", str(e)

    with session_scope() as s:
        run = s.get(PipelineRun, run_id)
        run.status, run.error, run.stage = status, error, None
        run.finished_at = now()
        run.stats = dict(stats)
    return {"run_id": run_id, "status": status, "error": error, **stats}
