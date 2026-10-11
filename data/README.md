# Dataset

Snapshot from SignalScout pipeline runs on 9–11 October 2026, and exported with
`uv run signalscout export`.

| File | Rows | Contents |
|---|---|---|
| `leads.csv` | 55 | One row per company: score, latest round, best contact, people, why-now reasons. Same shape as the in-app CSV export (CRM import ready) |
| `leads.json` | 55 | Full lead records: score breakdown, all validated emails/phones with confidence, socials, every funding event with investors and source article ids |
| `articles_index.csv` | 50 | Every scraped article: source, date, title, URL, and how the pipeline classified it (`is_company_funding`, `skip_reason` = `prefilter` / `not_company_funding`) |

## Funnel in this snapshot

```
50 articles scraped from 4 sources
 ├─ 12 dropped by the keyword pre-filter (no LLM call)
 ├─ 13 read by the LLM and rejected (VC fund closes, event promos, analysis pieces)
 └─ 25 funding articles ──► 56 rounds extracted (round-ups contain several)
                              └─ 3 duplicate rounds merged across outlets
                                   └─ 55 companies
                                        ├─ 38 with a verified website (11 linked in the article, 27 matched + verified)
                                        ├─ 17 left without a website rather than risk a wrong match
                                        └─ 15 with a verified email on the company's own domain (MX-checked)
```

## What is not included

The full text of the news articles is deliberately excluded: it is the publishers' copyrighted
content. Each article is referenced by URL instead, and the pipeline can regenerate everything
from the live feeds (`uv run signalscout run`).

All contact details are business contacts published on the companies' own public websites.
Personal names come from published press coverage.
