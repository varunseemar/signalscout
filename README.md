# SignalScout

**SaaSquatch tells you who exists. SignalScout tells you who to contact today, and why.**

SignalScout is a lead engine built on *buying signals*. It watches startup funding news, uses AI to pull out who raised, how much, from whom and for what, finds each company's contact details on its own website, and ranks every lead against your Ideal Customer Profile. Each score comes with a plain-English reason.

A company that just raised money has fresh budget, a hiring plan and a mandate to grow. That is the best moment to reach it, and static lead databases can't show it.

| | |
|---|---|
| **Architecture & UX write-up** | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): UX decisions, backend architecture, database, caching, hosting, deployment, cloud provider, exact versions |
| **API demo (Jupyter)** | [notebooks/api_walkthrough.ipynb](notebooks/api_walkthrough.ipynb): executed walkthrough of the live API, outputs included |
| **Dataset** | [data/](data/): 55 scored leads (CSV + JSON) and the 50-article index |
| **Setup** | [Running locally](#running-locally) |

---

## Why this feature (business case)

SaaSquatch's flow is *search → filter → enrich → export*. It returns a lot of rows, but a rep still has to decide who to call first. SignalScout adds what comes before outreach: **prioritisation by timing and fit**.

| Sales problem | What SignalScout does |
|---|---|
| "Which of these 500 leads should I call?" | 0–100 score = ICP fit (40) + timing (25) + deal size (15) + reachability (20), with reasons |
| "Why would they talk to me now?" | Every lead has a funding *trigger*: round, amount, lead investors, use of funds |
| Irrelevant rows waste rep time | AI drops non-leads (VC fund closes, opinion pieces, events). A keyword pre-filter skips obvious noise before any LLM spend |
| Bounced emails hurt sender reputation | Emails are MX-checked and labelled *Verified / Deliverable / Risky*. Role inboxes are flagged |
| Same deal shows up 3 times | Articles are deduplicated three ways, and companies and rounds are merged across outlets |
| Leads have to land in the CRM | CSV export with HubSpot/Salesforce-style headers. Status tracking (new → shortlisted → contacted) |
| Generic outreach gets ignored | One click writes a first-touch email that references the actual round and your offer |

The ICP editor (sectors, stages, countries, round size, how fast a signal fades) re-scores every lead immediately, without re-scraping.

---

## Architecture

```
            GitHub Actions cron / "Find new leads" button
                              │
   ┌──────────────────────────▼───────────────────────────┐
   │  Scrapy crawl (4 sources, RSS + article pages)       │
   │  seen-URL skip (Postgres) → validation (pydantic)    │
   │  → title+date dupe filter → idempotent upsert        │
   │  → per-source health record (ok / warning / broken)  │
   └──────────────────────────┬───────────────────────────┘
                              ▼
   keyword pre-filter ──► Gemini structured extraction (JSON schema)
                              ▼
   entity resolution: company by domain → name → fuzzy; rounds merged across outlets
                              ▼
   async website enrichment (robots.txt-aware): emails, phones, socials, hiring
                              ▼
   validation: MX lookup, role vs personal, E.164 phones → data-quality score
                              ▼
   ICP scoring with reasons ──► Postgres ──► FastAPI ──► Next.js dashboard
```

### Stack

| Layer | Technology | Why |
|---|---|---|
| Scraping | **Scrapy 2.19**, feedparser, parsel, w3lib | Mature crawler with built-in politeness, retries, robots.txt and stats |
| AI | **Google Gemini** (`gemini-3.5-flash-lite`, with a fallback chain of other models) via `google-genai`, Pydantic response schemas | Typed JSON output, no regex parsing of LLM text. Fast (~3 s per article) and runs on the free tier |
| Enrichment | **httpx** (async), dnspython, phonenumbers, tldextract, rapidfuzz | Concurrent website crawl, MX validation, phone normalisation, fuzzy dedupe |
| API | **FastAPI** + Uvicorn, SQLAlchemy 2.0 | Typed, fast to build, auto-generated OpenAPI docs at `/docs` |
| Database | **PostgreSQL 17** (JSONB for contacts/reasons) | Relational core + flexible enrichment payloads, `ON CONFLICT` upserts |
| Frontend | **Next.js 16** (App Router), React 19, **Tailwind CSS v4**, SWR, lucide-react | Static shell + client-side data, optimistic updates |
| Infra | Docker Compose (local DB), uv (Python packaging) | One-command setup |

### Data model

- `articles`: one row per scraped URL (`url_hash` = SHA-1 of the canonical URL, unique)
- `companies`: one row per real company (unique `domain`), with enrichment, score and workflow status
- `funding_events`: one row per round. `article_ids` lists every outlet that covered it
- `icp_profile`: the user's scoring preferences
- `pipeline_runs`, `spider_health`: observability

### Data quality (deduplication, validation, enrichment)

1. **Seen-URL skip:** before downloading, each spider loads the URL hashes it has already stored, so a repeat run only fetches new articles. The list lives in Postgres rather than a local file, so it works on ephemeral or serverless runners.
2. **Schema validation:** every item must satisfy `ArticleItem` (title ≥ 5 chars, body ≥ 200 chars, valid URL). Failures are counted per field. If half or more of a source's items fail, the source is flagged as having stale selectors.
3. **In-run dupe filter:** a title + date fingerprint catches syndicated copies under different URLs.
4. **Idempotent insert:** `ON CONFLICT (url_hash) DO NOTHING`, so a crawl can be re-run safely.
5. **Entity resolution:** companies are matched on registered domain, then normalised name (suffixes like *Inc/Labs/AI* stripped), then fuzzy ratio ≥ 92. A round is merged when it's the same company within 45 days with the same round type or an amount within 15%.
6. **Contact validation:** live MX lookup (cached per domain), same-domain check, role-inbox detection, junk/asset filtering, and phone validity plus E.164 formatting.
7. **Websites are verified, not guessed:** the company site comes from the LLM, or from a link in the article whose domain matches the company name. Otherwise the pipeline tries `name.com/.ai/.io/.co`, and accepts a candidate only if the name appears in the page title **and** the homepage shares at least 2 topic words with the article's description of the company. Borderline candidates get a yes/no check from the LLM, and login walls and parked domains are rejected outright. This stopped "Wally" (a dental startup) from being matched to a yacht builder, and "Meticulous" from being matched to the wrong company. When unsure, the lead is left without a website rather than given a wrong one, and the UI labels guessed sites *matched by name*.

### Reliability and handling site changes

- **Fallback selectors:** each spider lists several CSS selectors per field and uses the first that matches.
- **RSS first:** feeds change far less often than page markup. Two sources need no HTML parsing at all.
- **Per-source health:** 0 feed entries → *broken*; ≥ 50% validation failures → *warning*. Shown live in the header.
- **Debug a single article:** `scrapy crawl techcrunch -a debug_url=<url>`.
- **Retries:** Scrapy retries on 429/5xx with AutoThrottle. Gemini calls use the server's own retry delay on per-minute limits.
- **LLM quota resilience:** a shared rate limiter keeps the pipeline under the free tier's requests-per-minute limit, so it doesn't burn retries. When a model's *daily* quota is spent, calls move to the next model in `GEMINI_FALLBACK_MODELS` instead of waiting an hour.
- **Isolation:** one bad company website can't fail the batch, and a failed LLM call leaves the article queued for the next run.

### Performance and cost

- A keyword pre-filter removes obvious non-funding articles before any LLM call.
- `MAX_EXTRACT_PER_RUN` limits LLM spend per run. Lite models are the default. Full models fall back with `thinking_level=low` (≈3× fewer tokens).
- Each LLM result is committed as soon as it returns, so a crash mid-run keeps everything already paid for and the UI shows progress.
- LLM calls run in a thread pool. Website enrichment runs fully async with a semaphore.
- Enrichment is cached per company for `ENRICH_TTL_DAYS` (7). Email drafts are cached until regenerated.
- The ICP change path is pure SQL + Python re-scoring, so no re-scraping or LLM calls are needed.

### Ethical data collection

- `ROBOTSTXT_OBEY=True` for news sites, and the enrichment crawler checks `robots.txt` per company domain.
- Only public business information is collected: company websites, published press, and a company's own contact details.
- No LinkedIn scraping. People are linked to a LinkedIn *search* instead.
- Rate-limited (AutoThrottle, ≤ 4 concurrent requests per domain, enrichment capped at 5 pages per site), with an identifying user agent for company-site crawls.

---

## Running locally

**Requirements:** Docker, Python 3.12 + [uv](https://docs.astral.sh/uv/), Node 20+, and a [Gemini API key](https://aistudio.google.com/apikey).

```bash
# 1. Database
docker compose up -d db

# 2. Backend
cd backend
cp .env.example .env            # then set GEMINI_API_KEY
uv sync
uv run signalscout run          # crawl + extract + enrich + score (first run takes a few minutes)
uv run uvicorn signalscout.api.main:app --reload --port 8000   # API docs: http://localhost:8000/docs

# 3. Frontend (new terminal)
cd web
npm install
npm run dev                     # http://localhost:3000
```


### CLI

| Command | What it does |
|---|---|
| `uv run signalscout crawl [source...]` | Run spiders only (`techcrunch`, `prnewswire`, `geekwire`, `alleywatch`) |
| `uv run signalscout process` | Extract → resolve → enrich → score any unprocessed articles |
| `uv run signalscout run` | Full pipeline, recorded as a pipeline run |
| `uv run signalscout rescore` | Recompute scores (after changing scoring code) |
| `uv run signalscout export` | Write the dataset to `data/` (CSV + JSON) |
| `uv run pytest` | Unit tests: normalisation, dedupe, website verification, email cleaning, scoring |

### Adding a news source

```python
class MySourceSpider(FeedSpider):
    name = "mysource"
    feed_urls = ["https://example.com/funding/feed/"]
    body_css = ("div.article-body", "article")   # fallbacks, first match wins
```

Then add it to `ALL_SPIDERS` in `backend/src/signalscout/scraper/spiders/sources.py`.

---

## Dataset

[`data/`](data/) contains a snapshot from a full pipeline run: 55 scored leads (`leads.csv`, `leads.json`) and the 50-article index with how each article was classified. Full article text is excluded because it is the publishers' copyrighted content. See [data/README.md](data/README.md) for the funnel.

## Project layout

```
backend/src/signalscout/
  scraper/      Scrapy settings, item contract, pipelines, spiders
  pipeline/     llm, extract, resolve, enrich, validate, score, outreach, orchestrator
  api/main.py   FastAPI app
  db.py         SQLAlchemy models
  cli.py        signalscout CLI
  export.py     dataset export
backend/tests/  pytest unit tests
data/           exported dataset
web/src/
  components/   Dashboard, FilterRail, LeadTable, LeadDrawer, IcpModal, Header, StatsBar
  lib/api.ts    API client + types
```

## Limitations and next steps

- Funding news skews toward venture-backed startups. Next sources: SEC Form D filings (covers private raises that never reach the press), job-board hiring spikes, and leadership changes.
- Contacts come from public company websites, so many startups only publish a role inbox. A paid email-finder (Hunter, Apollo) could plug into `enrich.py`.
- A direct HubSpot push (API key + one endpoint) would replace the CSV step.
- Scheduled runs: GitHub Actions cron calling `signalscout run` against the hosted DB.

## Demo notebook

With the API running, re-execute the walkthrough:

```bash
cd backend
uv run jupyter nbconvert --to notebook --execute --inplace ../notebooks/api_walkthrough.ipynb
```
