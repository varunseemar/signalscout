from contextlib import contextmanager
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from signalscout.config import get_settings

JsonType = JSON().with_variant(JSONB(), "postgresql")

engine = create_engine(get_settings().database_url, pool_pre_ping=True, pool_size=5, max_overflow=5)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Article(Base):
    """One scraped news article. url_hash = sha1(canonical url) makes inserts idempotent."""

    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    url_hash: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    url: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(40), index=True)
    title: Mapped[str] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[date | None] = mapped_column(Date, index=True)
    text: Mapped[str] = mapped_column(Text)
    outbound_links: Mapped[list] = mapped_column(JsonType, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Set by the extraction step
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    is_funding: Mapped[bool | None] = mapped_column(Boolean)
    skip_reason: Mapped[str | None] = mapped_column(String(80))


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    name_key: Mapped[str] = mapped_column(String(200), index=True)
    domain: Mapped[str | None] = mapped_column(String(253), unique=True)
    website: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    sector: Mapped[str | None] = mapped_column(String(80), index=True)
    hq_city: Mapped[str | None] = mapped_column(String(120))
    hq_country: Mapped[str | None] = mapped_column(String(80), index=True)

    # Enrichment (website crawl) + validation results
    emails: Mapped[list] = mapped_column(JsonType, default=list)
    phones: Mapped[list] = mapped_column(JsonType, default=list)
    socials: Mapped[dict] = mapped_column(JsonType, default=dict)
    people: Mapped[list] = mapped_column(JsonType, default=list)
    website_source: Mapped[str | None] = mapped_column(String(20))  # article | guessed
    site_title: Mapped[str | None] = mapped_column(Text)
    meta_description: Mapped[str | None] = mapped_column(Text)
    hiring: Mapped[bool | None] = mapped_column(Boolean)
    enrich_status: Mapped[str] = mapped_column(String(30), default="pending")
    enriched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Scoring
    score: Mapped[int] = mapped_column(Integer, default=0, index=True)
    score_breakdown: Mapped[dict] = mapped_column(JsonType, default=dict)
    score_reasons: Mapped[list] = mapped_column(JsonType, default=list)
    data_quality: Mapped[int] = mapped_column(Integer, default=0)

    # Sales workflow
    status: Mapped[str] = mapped_column(String(20), default="new", index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    email_draft: Mapped[dict | None] = mapped_column(JsonType)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    funding_events: Mapped[list["FundingEvent"]] = relationship(
        back_populates="company", order_by="FundingEvent.announced_on.desc()", cascade="all, delete-orphan"
    )


class FundingEvent(Base):
    """A funding round. Several articles about the same round collapse into one event."""

    __tablename__ = "funding_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    round_type: Mapped[str | None] = mapped_column(String(40))
    amount_usd: Mapped[float | None] = mapped_column(Float)
    valuation_usd: Mapped[float | None] = mapped_column(Float)
    investors: Mapped[list] = mapped_column(JsonType, default=list)
    lead_investors: Mapped[list] = mapped_column(JsonType, default=list)
    use_of_funds: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    announced_on: Mapped[date | None] = mapped_column(Date, index=True)
    article_ids: Mapped[list] = mapped_column(JsonType, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    company: Mapped[Company] = relationship(back_populates="funding_events")


class IcpProfile(Base):
    """Single-row table holding the user's Ideal Customer Profile used for scoring."""

    __tablename__ = "icp_profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    config: Mapped[dict] = mapped_column(JsonType, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    status: Mapped[str] = mapped_column(String(20), default="running")
    stage: Mapped[str | None] = mapped_column(String(40))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stats: Mapped[dict] = mapped_column(JsonType, default=dict)
    error: Mapped[str | None] = mapped_column(Text)


class SpiderHealth(Base):
    """Per-source crawl stats, used to surface broken scrapers in the UI (Spidermon-style)."""

    __tablename__ = "spider_health"
    __table_args__ = (UniqueConstraint("run_id", "source"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("pipeline_runs.id", ondelete="SET NULL"))
    source: Mapped[str] = mapped_column(String(40), index=True)
    feed_entries: Mapped[int] = mapped_column(Integer, default=0)
    items_new: Mapped[int] = mapped_column(Integer, default=0)
    items_skipped_seen: Mapped[int] = mapped_column(Integer, default=0)
    items_dropped: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="ok")
    message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def init_db() -> None:
    Base.metadata.create_all(engine)


@contextmanager
def session_scope():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
