# SignalScout backend

Python 3.12 package `signalscout`: Scrapy crawler, Gemini extraction, enrichment and validation, scoring, and the FastAPI app. See the [root README](../README.md) for setup and [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) for the design.

```bash
uv sync
uv run signalscout run                                    # crawl + extract + enrich + score
uv run uvicorn signalscout.api.main:app --port 8000       # API, docs at /docs
uv run pytest                                             # unit tests
```
