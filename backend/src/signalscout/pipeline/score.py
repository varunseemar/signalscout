"""
Lead score (0-100) = ICP fit (40) + timing (25) + deal size (15) + reachability (20).
Every point comes with a plain-English reason so reps trust (and can argue with) the ranking.
"""

from datetime import date

DEFAULT_ICP = {
    "pitch": "We help newly funded startups scale their go-to-market with outbound lead generation.",
    "sectors": ["AI / ML", "SaaS / Software", "Fintech", "Cybersecurity", "Healthcare / Biotech"],
    "countries": ["United States"],
    "stages": ["Seed", "Series A", "Series B"],
    "min_amount_usd": 2_000_000,
    "max_amount_usd": 100_000_000,
    "max_age_days": 45,
}


def _money(v: float) -> str:
    return f"${v / 1e9:.1f}B" if v >= 1e9 else f"${v / 1e6:.0f}M" if v >= 1e6 else f"${v / 1e3:.0f}K"


def score_company(company, latest_event, icp: dict, today: date | None = None) -> tuple[int, dict, list[str]]:
    today = today or date.today()
    icp = {**DEFAULT_ICP, **(icp or {})}
    reasons: list[str] = []
    b = {"fit": 0, "timing": 0, "size": 0, "reachability": 0}

    # --- ICP fit (40) ---
    if company.sector and company.sector in icp["sectors"]:
        b["fit"] += 20
        reasons.append(f"Target sector: {company.sector}")
    if company.hq_country and (not icp["countries"] or company.hq_country in icp["countries"]):
        b["fit"] += 10
        reasons.append(f"In target geography ({company.hq_city + ', ' if company.hq_city else ''}{company.hq_country})")
    stage = latest_event.round_type if latest_event else None
    if stage and stage in icp["stages"]:
        b["fit"] += 10
        reasons.append(f"Target stage: {stage}")

    # --- Timing (25): fresh money decays over max_age_days ---
    if latest_event and latest_event.announced_on:
        age = max(0, (today - latest_event.announced_on).days)
        b["timing"] = round(25 * max(0.0, 1 - age / icp["max_age_days"]))
        when = "today" if age == 0 else "yesterday" if age == 1 else f"{age} days ago"
        amount = _money(latest_event.amount_usd) + " " if latest_event.amount_usd else ""
        reasons.insert(0, f"Raised {amount}{stage or ''} {when}".replace("  ", " "))
    if company.hiring:
        b["timing"] = min(25, b["timing"] + 3)
        reasons.append("Actively hiring - budget is being deployed")

    # --- Deal size (15) ---
    amount = latest_event.amount_usd if latest_event else None
    if amount is None:
        b["size"] = 5
    elif icp["min_amount_usd"] <= amount <= icp["max_amount_usd"]:
        b["size"] = 15
    elif amount > icp["max_amount_usd"]:
        b["size"] = 8  # big rounds = big budgets, but harder to break into
    else:
        b["size"] = 4

    # --- Reachability (20) ---
    b["reachability"] = round(company.data_quality * 0.2)
    if any(e["confidence"] == "high" for e in company.emails):
        reasons.append("Verified email on company domain")
    elif not company.emails:
        reasons.append("No public email found yet")

    total = min(100, sum(b.values()))
    return total, b, reasons
