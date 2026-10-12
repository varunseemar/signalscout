# SignalScout: Design & Architecture

This document covers the UX design choices and the full backend architecture: data storage, caching and performance, hosting, deployment, cloud provider, and the exact technologies used.

- [1. Product context](#1-product-context)
- [2. UX design choices](#2-ux-design-choices)
- [3. System architecture](#3-system-architecture)
- [4. Data storage strategy](#4-data-storage-strategy)
- [5. Caching & performance optimizations](#5-caching--performance-optimizations)
- [6. Hosting setup (static vs. serverless)](#6-hosting-setup-static-vs-serverless)
- [7. Deployment process](#7-deployment-process)
- [8. Cloud provider](#8-cloud-provider)
- [9. Exact technology stack](#9-exact-technology-stack)
- [10. Reliability, data quality & ethics](#10-reliability-data-quality--ethics)

---

## 1. Product context

SaaSquatch Leads returns *lists* of companies (search → filter → enrich → export). A sales rep still has to decide **who to contact first and what to say**. SignalScout adds a prioritisation layer built on **buying signals**: a company that just raised money has new budget, a hiring plan and pressure to grow.

The user's job is: *"Each morning, show me the handful of companies worth contacting today, why each one is worth it, and give me what I need to reach them."* Every design decision below follows from that.

---

## 2. UX design choices

### 2.1 Information architecture: one screen, ranked list plus detail drawer

| Choice | Why |
|---|---|
| **A single dashboard, no page navigation** | Sales triage is a loop: scan, open, act, next. Separate pages would break that loop. Everything is one click from the list. |
| **Ranked by score by default** ("Best match") | Answers "who first?" before the user does anything. Other sorts (most recent, largest round, name) are one dropdown away. |
| **Detail opens in a side drawer**, not a new page | The list stays visible and keeps its scroll position and filters. `Esc` or a backdrop click closes it, and the row stays highlighted so the user doesn't lose their place. |
| **Status tabs**: All active / New / Shortlisted / Contacted / Dismissed | A lightweight pipeline inside the tool. Dismissed leads leave the main view without being deleted, so nothing is lost. |

### 2.2 Clear presentation: every number explains itself

- **Score badge, colour-coded** (green ≥ 80 *hot*, amber ≥ 60 *warm*, grey *cold*). Green, amber and grey are the only signal colours in the UI, so they stand out. The brand colour (indigo) is reserved for actions.
- **A "Why now" column** shows the AI's one-line reason (e.g. *"Raised $24M Series A to expand manufacturing"*). The rep reads *why* before opening anything.
- **Score breakdown in the drawer**: four bars (ICP fit 40 / Timing 25 / Deal size 15 / Reachability 20) plus plain-English reasons (*"Target sector: Fintech"*, *"Raised $25M Series A yesterday"*, *"Verified email on company domain"*). A score the user can't inspect isn't trusted, and the breakdown lets a rep disagree with it for a concrete reason.
- **Reachability icons** in each row (email / phone / LinkedIn / hiring). Green means verified, amber means usable but unverified, grey means missing. "Can I actually reach them?" is answered without opening the lead.
- **Email confidence labels** (*Verified*, *Deliverable*, *Risky*), each with a tooltip explaining the check behind it. Role inboxes (`info@`, `sales@`) are tagged so reps can prefer a named person.
- **Honest data labels**: a website found by matching the company name (rather than linked in the article) is tagged *matched by name*. When no contact exists, the drawer says *why* (no website found, site unreachable or blocked by robots.txt, or no public email) and points to the people listed instead.
- **Typography**: Geist Sans plus Geist Mono for emails and phone numbers, `tabular-nums` for scores and money so columns line up, `$24M` / `$2.5B` money formatting, and relative dates (*"3d ago"*) for freshness.

### 2.3 Guiding users through key processes

| Process | How the UI guides it |
|---|---|
| **First run** | The empty state is an onboarding card: three steps (watch news, extract and enrich, rank) and one primary button, *Find new leads*. |
| **Running the pipeline** | The button turns into a spinner, and the header shows the live stage (*Crawling news sources… → Extracting funding rounds with AI… → Enriching company websites… → Scoring leads…*). The list refreshes automatically when the run finishes. |
| **Filtering** | A left filter rail with chips (stage, sector), a recency selector (7 / 14 / 30 days / any), a minimum-score slider, a *Has an email* toggle and search. *Clear filters* appears only when something is set, and a "no matches" state offers a one-click reset. |
| **Verifying leads** | Confidence labels, the score breakdown and links to every source article ("Reported by 2 outlets (merged)") let the rep verify a lead in seconds. |
| **Exporting** | *Export CSV* exports the **current filtered view**, or only the **checked rows** if any are selected (the label changes to *Export 3*). Column names match HubSpot and Salesforce company and contact import fields. |
| **Outreach** | *Write email with AI* drafts a short first-touch email that references the actual round and the user's own offer. *Copy* or *Open in mail* (a pre-filled `mailto:` to the best email) sends it. The contact hint suggests who to send it to and why. |
| **Tuning the ICP** | The *Ideal customer* modal (sectors, stages, countries, round size, how fast a signal fades, "what do you sell?") shows how many points each criterion is worth. *Save & re-score* re-ranks every lead immediately, with no re-scraping. |

### 2.4 Time-saving automation and workflow touches

- **Optimistic updates**: starring or dismissing a lead updates the row instantly. The server call happens in the background.
- **Scraper health indicator** in the header (green, amber or red dot): if a news source breaks, the user can see why leads have dried up.
- **Notes autosave** when the field loses focus. **Email drafts are cached** per lead, so reopening one is instant and costs no LLM call.
- **Bulk selection** with select-all for exporting a subset.

### 2.5 Public demo mode

When `ADMIN_TOKEN` is set on the API, the deployment is **read-only for visitors**. They can browse, filter, open leads, export CSVs and generate AI email drafts (limited to `EMAIL_DRAFTS_PER_HOUR` per visitor IP, and cached drafts are free). Running the pipeline, changing the ICP and editing lead status or notes return `403` and are hidden in the UI, replaced by a *Read-only demo* badge. The owner unlocks editing once by visiting `/?admin=<token>`: the key is stored in `localStorage`, removed from the URL, and sent as an `X-Admin-Token` header. Data stays fresh through the scheduled GitHub Actions run.

A Render free-tier instance sleeps when idle, so if the first API response takes more than 4 s the dashboard shows a *"Waking up the API server…"* notice instead of an endless loading skeleton.

### 2.6 Responsiveness & accessibility

- The table collapses to a compact two-line row below the `lg` breakpoint, and the filter rail stacks above the list. The drawer is full-width on phones.
- Semantic roles (`table`, `row`, `dialog` with `aria-modal`), `aria-label` on every icon-only button, `aria-pressed` on filter chips, and visible `focus-visible` rings.
- Skeleton loaders instead of spinners for the list, so the layout doesn't jump when data arrives.

---

## 3. System architecture

```
                     ┌────────────────────────────── Scheduler ───────────────────────────────┐
                     │  GitHub Actions cron (every 6h)   or   "Find new leads" button (UI→API)  │
                     └─────────────────────────────────────┬──────────────────────────────────┘
                                                           ▼
┌─────────────────────────────── Ingestion: Scrapy 2.19 (child process) ────────────────────────────┐
│ 4 spiders on one FeedSpider base: TechCrunch, PR Newswire (RSS → article page)                     │
│                                    GeekWire, AlleyWatch (RSS full text)                           │
│ seen-URL skip (Postgres) → ValidationPipeline (pydantic) → DupeFilterPipeline → PostgresPipeline  │
│ HealthRecorder extension → spider_health (ok / warning / broken)                                  │
└───────────────────────────────────────────────┬───────────────────────────────────────────────────┘
                                                ▼  articles
┌─────────────────────────── Processing: Python orchestrator ─────────────────────────────┐
│ 1. Pre-filter (regex) ─► 2. Gemini structured extraction (thread pool + RPM limiter)    │
│ 3. Entity resolution: domain → name key → fuzzy (+ same-round check) ; round merge      │
│ 4. Website enrichment (async httpx, robots.txt, ≤5 pages/site, verified site matching)  │
│ 5. Validation: MX lookup, role/personal, E.164 phones → data_quality                    │
│ 6. ICP scoring with reasons                                                             │
└───────────────────────────────────────────────┬─────────────────────────────────────────┘
                                                ▼
                                   PostgreSQL 17 (relational + JSONB)
                                                ▲
┌───────────────────────── API: FastAPI 0.143 + Uvicorn ─────────────────────────┐
│ /api/leads (filter/sort)  /api/leads/{id}  PATCH status/notes                  │
│ /api/leads/{id}/email-draft (Gemini, cached)  /api/export.csv                  │
│ /api/icp (GET/PUT → re-score)  /api/pipeline/run|runs  /api/health/sources     │
│ /api/stats  · OpenAPI docs at /docs                                            │
└───────────────────────────────────────────────┬────────────────────────────────┘
                                                ▼  JSON over HTTPS (CORS allow-list)
┌───────────── Web: Next.js 16 static shell + React 19 client components ─────────────┐
│ SWR data layer · Tailwind CSS v4 · lucide-react icons · Geist fonts                 │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### Key backend design decisions

| Decision | Rationale |
|---|---|
| **Crawl runs as a child process** (`python -m signalscout.cli crawl`) | Scrapy's Twisted reactor can't be restarted inside a long-lived API process. A subprocess isolates crawl crashes and memory from the API. |
| **Processing is separate from crawling** | The LLM and enrichment steps can be re-run (`signalscout process`) on stored articles without hitting the news sites again. |
| **LLM output is typed** | Gemini is given a Pydantic schema (`response_schema`) and returns validated objects. Fixed enums for sector and round type keep the filters consistent. |
| **One `PipelineRun` row per run** with `stage` and `stats` | The UI shows live progress and run history without a message queue. |
| **Scoring is pure Python over stored data** | Changing the ICP re-scores 55 leads in milliseconds with no network calls, which is why *Save & re-score* is instant. |

---

## 4. Data storage strategy

**Database: PostgreSQL** (17 locally via `postgres:17-alpine` in Docker Compose; **18 on Neon** in production, a managed serverless Postgres). Access is through **SQLAlchemy 2.1** with the **psycopg 3** driver.

**Why Postgres:** leads are naturally relational (company → funding events → source articles) and need unique constraints for deduplication. Enrichment output (lists of emails with metadata, socials, people) varies in shape. Postgres handles both: relational tables for identity and joins, and **JSONB** for the variable payloads. A document store would make the unique-key deduplication harder, and a pure relational schema would need 5+ extra tables for contact details.

| Table | Purpose | Key constraints / indexes |
|---|---|---|
| `articles` | Every scraped article | `url_hash` **UNIQUE** (SHA-1 of the canonical URL) → idempotent `INSERT … ON CONFLICT DO NOTHING`. Indexes on `source`, `published_at`, `processed_at` (the work queue) |
| `companies` | One row per real company | `domain` **UNIQUE**. Indexed `name_key` (normalised name for matching), `score`, `status`, `sector`, `hq_country`. JSONB: `emails`, `phones`, `socials`, `people`, `score_breakdown`, `score_reasons`, `email_draft` |
| `funding_events` | One row per round; several articles about the same round collapse into one | FK → companies (cascade). `article_ids` JSONB lists every outlet that covered it. Indexed `announced_on` |
| `icp_profile` | Single-row user configuration | JSONB `config` |
| `pipeline_runs` | Run status, stage, stats, error | Polled by the UI |
| `spider_health` | Per-source, per-run crawl stats and status | Feeds the health indicator |

- **Articles table as a work queue:** `processed_at IS NULL` means "not yet extracted". A failed LLM call leaves the article NULL, so it's retried on the next run. No separate queue infrastructure is needed.
- **Fill blanks, never overwrite:** when a second article mentions the same company, only empty fields are filled, so a thin article can't erase good data.
- **Schema creation:** `Base.metadata.create_all()` on startup. Alembic migrations would be the next step for production schema changes.

---

## 5. Caching & performance optimizations

### Caching layers

| Layer | What is cached | Where | Effect |
|---|---|---|---|
| **Seen-URL set** (DeltaFetch equivalent) | Hashes of every stored article per source | Loaded from Postgres when a spider starts | Repeat crawls download **only new articles**. A rerun of a 10-entry feed made 0 article requests (`feed/skipped_seen: 10`). Stored in the DB, not a local file, so it works on ephemeral CI runners |
| **Enrichment TTL** | A company's website crawl results | `companies.enriched_at` (7-day TTL, `ENRICH_TTL_DAYS`) | Each company's site is crawled at most once a week. Errors aren't cached, so they retry |
| **MX lookups** | DNS MX result per email domain | In-process `functools.lru_cache` (2,048 entries) | One DNS query per domain per run |
| **robots.txt** | Parsed rules per host | In-memory dict per enrichment batch | One robots fetch per site |
| **AI email drafts** | Generated subject and body | `companies.email_draft` (JSONB) | Reopening a lead costs no LLM call. *Regenerate* bypasses the cache |
| **Scrapy HTTP cache** | Raw responses | `.scrapy/httpcache` (dev only, 1h) | Instant selector iteration during development |
| **Client cache** | API responses | SWR in the browser (`keepPreviousData`) | Changing a filter keeps the old list on screen while the new one loads. Shared keys mean no duplicate requests |

### Performance and cost optimizations

- **LLM pre-filter:** a keyword regex removes obvious non-funding news before any LLM call. In the snapshot, 12 of 50 articles (24%) were dropped for free.
- **Model choice:** `gemini-3.5-flash-lite` takes about 2.7 s per article, compared with about 116 s on `gemini-3.8-flash` (thinking model plus free-tier queueing), with the same extraction quality on the test articles. Full models in the fallback chain run with `thinking_level=low` (≈3× fewer thinking tokens).
- **Concurrency with a shared rate limiter:** LLM calls run in a 4-thread pool, and a token-spacing limiter (`LLM_REQUESTS_PER_MINUTE=12`) keeps them under the free tier's 15 RPM. Before the limiter, a run hit 60 HTTP 429s and lost 6 articles. After it, zero.
- **Quota-aware model fallback:** a *daily* quota error immediately switches to the next model in `GEMINI_FALLBACK_MODELS` instead of sleeping. A *per-minute* error waits for the server's suggested retry delay.
- **Incremental commits:** each LLM result is committed as soon as it returns, so a crash keeps paid-for work and progress is visible.
- **Async enrichment:** `httpx.AsyncClient` with an 8-way semaphore, connection pooling, 12 s timeouts, and at most 5 pages per site (home plus up to 4 contact/about/team/careers pages).
- **Database:** indexes on every filter/sort column, `selectinload` for funding events (avoids N+1 queries in the lead list), and `pool_pre_ping` with a bounded pool (5 + 5 overflow).
- **Frontend:** the page is **prerendered as a static shell** (`○ (Static)` in the build output), so the first paint needs no server. Data loads client-side. `useDeferredValue` keeps typing in search responsive. Pipeline status polls every 1.5 s **only while a run is active** and stops otherwise.
- **Measured end to end:** a full `signalscout run` (crawl 4 sources → 37 LLM extractions → 45 website enrichments → scoring) takes **about 5 minutes on the free tier**, most of it waiting on the deliberate rate limiting.

---

## 6. Hosting setup (static vs. serverless)

Each layer runs on the hosting model that suits its workload:

| Component | Hosting model | Target platform | Why this model |
|---|---|---|---|
| **Web (Next.js)** | **Static** shell on a global CDN | **Vercel** | The page is fully prerendered and all data is fetched client-side, so it can be served from the edge with no server runtime |
| **API (FastAPI)** | **Long-running container** (not serverless functions) | **Render** web service (Docker, `render.yaml`) | `POST /api/pipeline/run` starts a background job that runs for minutes and spawns a Scrapy subprocess. Serverless functions time out and can't hold background threads. A small always-on container is simpler and more predictable |
| **Scheduled pipeline** | **Serverless batch** (ephemeral runner) | **GitHub Actions** cron (`.github/workflows/pipeline.yml`, every 6 h) | Runs `signalscout run` against the managed DB and then disappears, so there's no idle compute. The DB-backed seen-URL set is what makes stateless runners work |
| **Database** | **Serverless Postgres** (scales to zero) | **Neon** | Managed Postgres 17, autoscaling compute, free tier, standard connection string, so there are no code changes |

**Configuration:** everything is 12-factor environment variables read by `pydantic-settings`: `DATABASE_URL` (a plain `postgres://` / `postgresql://` URL from Neon is rewritten to the psycopg driver automatically), `GEMINI_API_KEY`, `GEMINI_MODEL`, `GEMINI_FALLBACK_MODELS`, `CORS_ORIGINS`, `ADMIN_TOKEN`, `EMAIL_DRAFTS_PER_HOUR`, `MAX_EXTRACT_PER_RUN`, `LLM_REQUESTS_PER_MINUTE` on the backend, and `NEXT_PUBLIC_API_URL` on the frontend. Secrets live in each platform's secret store, never in the repo.

---

## 7. Deployment process

> **Status: live.** Web: https://signalscout-seven.vercel.app · API: https://signalscout-api.onrender.com/docs · DB: Neon Postgres 18 (AWS us-west-2) · Refresh: GitHub Actions every 6 h. The steps below are the one-time setup that was used.

1. **Database (Neon):** create a project (Postgres 18, AWS US West to sit next to Render's Oregon region) and copy the **direct** connection string, the host *without* `-pooler`. The app keeps its own SQLAlchemy connection pool, and Neon's PgBouncer pooler (transaction mode) can leak session settings between clients. During the initial `pg_dump | psql` seed, the dump's `set_config('search_path', '')` stuck to pooled server connections and made every table "not exist" for the app. Tables are created automatically on the API's first start, or seeded from the local DB with `pg_dump --no-owner | psql "$NEON_URL"`.
2. **API (Render):** *New → Blueprint →* select this repo. Render reads `render.yaml`, builds `backend/Dockerfile` (`python:3.12-slim` + `uv sync --frozen`, with the lock file guaranteeing identical versions), and asks for `DATABASE_URL`, `GEMINI_API_KEY`, `CORS_ORIGINS` and `ADMIN_TOKEN`. The health check is `/api/stats`, and every push to `main` redeploys automatically.
3. **Web (Vercel):** import the repo with root directory `web/` and set `NEXT_PUBLIC_API_URL=https://<render-service>.onrender.com`. Vercel builds with `next build` and deploys previews per branch and production from `main`.
4. **Scheduler (GitHub Actions):** add `DATABASE_URL` and `GEMINI_API_KEY` as repository secrets. The workflow runs every 6 hours, or manually via *Run workflow* (`workflow_dispatch`).
5. **CI quality gates** (run locally before every commit): `uv run pytest` (15 tests: pipeline logic plus API access control), `npx tsc --noEmit`, `npm run lint`, `npm run build`.

**Release flow:** push to `main` → Render rebuilds the API container and Vercel rebuilds the static site in parallel. The scheduled workflow always checks out the latest `main`.

---

## 8. Cloud provider

The target stack uses managed platforms rather than a hand-configured VPC, so a small team runs no servers:

| Service | Runs on |
|---|---|
| Vercel (web, CDN) | AWS (Vercel's infrastructure is built on AWS) |
| Neon (Postgres) | AWS (e.g. `aws-us-east-1`) |
| Render (API container) | Render's managed cloud |
| GitHub Actions (scheduler) | GitHub-hosted runners (Microsoft Azure) |
| Google Gemini API (LLM) | Google Cloud |

**Primary cloud: AWS** (web and data). **Why not raw AWS (ECS/RDS/Lambda)?** For a product at this stage, managed platforms give push-to-deploy, preview environments, TLS and autoscaling at no cost and with no infrastructure code. The app is a standard Docker container plus Postgres, so moving to AWS ECS Fargate + RDS (or GCP Cloud Run + Cloud SQL) later only means changing environment variables, not code.

---

## 9. Exact technology stack

### Backend (Python 3.12, packaged with uv 0.12)

| Purpose | Library | Version |
|---|---|---|
| Crawling framework | Scrapy | 2.19.0 |
| RSS parsing | feedparser | 6.0.14 |
| HTML selection / cleaning | parsel / w3lib | 1.12.1 / 2.5.0 |
| HTTP client (async enrichment) | httpx | 0.28.1 |
| LLM SDK | google-genai (Gemini API) | 2.29.0 |
| Data validation / LLM schemas / settings | pydantic / pydantic-settings | 2.14.0 / 2.15.0 |
| ORM / DB driver | SQLAlchemy / psycopg (binary) | 2.1.4 / 3.3.6 |
| API framework / ASGI server | FastAPI / Uvicorn | 0.143.0 / 0.54.0 |
| Email MX validation | dnspython | 2.9.0 |
| Phone validation & E.164 | phonenumbers | 9.0.41 |
| Domain parsing (public suffix list) | tldextract | 5.4.0 |
| Fuzzy name matching | rapidfuzz | 3.14.6 |
| Tests | pytest | 9.1.1 |

**LLM models:** `gemini-3.5-flash-lite` (default) → fallback chain `gemini-3.1-flash-lite`, `gemini-flash-lite-latest`, `gemini-3.6-flash`, `gemini-3.7-flash`, `gemini-3.5-flash`, `gemini-3.8-flash`.

### Frontend (Node 22)

| Purpose | Library | Version |
|---|---|---|
| Framework (App Router, static prerender) | Next.js | 16.4.0 |
| UI library | React / React DOM | 19.3.0 |
| Language | TypeScript | 5.9.3 |
| Styling (CSS-first `@theme` tokens) | Tailwind CSS | 4.3.3 |
| Data fetching / cache | SWR | 2.5.1 |
| Icons | lucide-react (+ inline LinkedIn SVG) | 1.54.0 |
| Class composition | clsx | 2.1.1 |
| Fonts | Geist Sans / Geist Mono via `next/font` | — |
| Linting | ESLint 9 + eslint-config-next | 16.4.0 |

### Infrastructure

| Purpose | Technology |
|---|---|
| Database | PostgreSQL 17.11 locally (`postgres:17-alpine`), PostgreSQL 18 on Neon in production |
| Local orchestration | Docker Compose |
| API container | Docker (`python:3.12-slim` + uv) |
| Scheduling | GitHub Actions cron |
| Hosting | Vercel (web) · Render (API) · Neon (DB) |

---

## 10. Reliability, data quality & ethics

- **Three-layer deduplication:** seen-URL skip before download → title+date fingerprint within a run → `UNIQUE(url_hash)` in the DB. Then entity resolution at the company level (domain → normalised name → fuzzy match accepted only with a matching round) and the round level (same company ±45 days, same type or amount within 15%). Result: 3 duplicate rounds and 4 duplicate company mentions merged in the snapshot run.
- **Selector resilience:** RSS-first ingestion, fallback CSS selector lists per field, schema validation that turns silent breakage into counted errors, and per-source health status in the UI.
- **Website verification** (see README §Data quality): rejects same-name businesses, parked domains and login walls. Unit-tested with real failure cases.
- **Ethics:** `robots.txt` obeyed for news and company sites, AutoThrottle and per-domain concurrency limits, an identifying user agent for company-site crawls, no LinkedIn scraping (people link to a LinkedIn *search*), only public business contact data, and no full article text redistributed in the dataset.
