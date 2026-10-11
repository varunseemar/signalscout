"""Article -> structured funding rounds (Gemini), with a cheap keyword pre-filter in front."""

import re
from typing import Literal

from pydantic import BaseModel, Field

from signalscout.pipeline.llm import generate_json

SECTORS = [
    "AI / ML", "SaaS / Software", "Fintech", "Healthcare / Biotech", "Climate / Energy",
    "Hardware / Robotics", "Aerospace / Defense", "Cybersecurity", "Consumer", "E-commerce / Retail",
    "Real Estate / PropTech", "Logistics / Supply Chain", "Education", "Media / Entertainment",
    "Industrial / Manufacturing", "Other",
]
ROUNDS = [
    "Pre-Seed", "Seed", "Series A", "Series B", "Series C", "Series D+", "Growth",
    "Debt", "Grant", "Undisclosed",
]

Sector = Literal[tuple(SECTORS)]  # type: ignore[valid-type]
RoundType = Literal[tuple(ROUNDS)]  # type: ignore[valid-type]

# Skip the LLM entirely for articles that clearly aren't about a raise (saves cost + quota).
_FUNDING_HINT = re.compile(
    r"\b(rais(e|es|ed|ing)|funding|seed round|series [a-h]\b|pre-seed|investment round|"
    r"secures \$|closes \$|led by|valuation)\b",
    re.I,
)


class Person(BaseModel):
    name: str
    title: str | None = Field(None, description="e.g. 'Co-founder & CEO'")


class Round(BaseModel):
    company_name: str = Field(description="The operating company that raised money (not the investor)")
    website: str | None = Field(None, description="Company website if stated or linked; never guess")
    description: str = Field(description="One plain sentence: what the company does")
    sector: Sector
    hq_city: str | None = None
    hq_country: str | None = Field(None, description="Full country name, e.g. 'United States'")
    round_type: RoundType
    amount_usd: float | None = Field(None, description="Amount raised in US dollars (convert if needed)")
    valuation_usd: float | None = None
    lead_investors: list[str] = []
    investors: list[str] = Field([], description="All named investors including leads")
    use_of_funds: str | None = Field(None, description="What the money will be spent on, short phrase")
    people: list[Person] = Field(
        [], description="Founders/executives who WORK AT this company. Exclude investors, customers, analysts."
    )
    hiring: bool = Field(False, description="True if the article says they plan to hire or grow the team")
    why_now: str = Field(description="1-2 sentences a salesperson would use as the reason to reach out now")


class Extraction(BaseModel):
    rounds: list[Round] = Field(
        description="Funding rounds raised by operating companies. Empty if the article is not about one "
        "(e.g. a VC firm closing its own fund, acquisitions, opinion pieces, event promos)."
    )


SYSTEM = (
    "You extract startup funding events from news articles for a B2B sales team. "
    "Only report facts stated in the article. Use null when a value is not stated. "
    "A VC firm raising its own fund is NOT a company funding round. "
    "Amounts are plain numbers in USD, e.g. 24000000 for $24M."
)


def looks_like_funding(title: str, text: str) -> bool:
    return bool(_FUNDING_HINT.search(title) or _FUNDING_HINT.search(text[:1500]))


def extract_rounds(title: str, text: str, url: str, links: list[str]) -> Extraction:
    prompt = (
        f"URL: {url}\nTITLE: {title}\n"
        f"LINKS IN ARTICLE (one may be the company website): {', '.join(links[:15]) or 'none'}\n\n"
        f"ARTICLE:\n{text[:12000]}"
    )
    return generate_json(prompt, Extraction, system=SYSTEM)
