from pydantic import BaseModel, Field

from signalscout.pipeline.llm import generate_json


class EmailDraft(BaseModel):
    subject: str = Field(description="Under 8 words, no clickbait")
    body: str = Field(description="Under 120 words, plain text, ends with one low-friction question")
    contact_hint: str = Field(description="Who at the company this is best sent to, and why (one line)")


SYSTEM = (
    "You write short, specific cold emails for B2B sales reps. Reference the company's recent "
    "funding and what they'll use it for. No flattery, no buzzwords, no fake familiarity. "
    "Never invent facts that are not in the brief."
)


def draft_email(company, event, pitch: str) -> EmailDraft:
    people = ", ".join(f"{p['name']} ({p.get('title') or 'n/a'})" for p in company.people[:4]) or "unknown"
    brief = f"""SENDER'S OFFER: {pitch}

COMPANY: {company.name} - {company.description or ''}
SECTOR: {company.sector}   HQ: {company.hq_city or ''} {company.hq_country or ''}
ROUND: {event.round_type if event else 'n/a'} {f'${event.amount_usd:,.0f}' if event and event.amount_usd else ''}
LEAD INVESTORS: {', '.join(event.lead_investors) if event else ''}
USE OF FUNDS: {event.use_of_funds if event else ''}
HIRING: {'yes' if company.hiring else 'unknown'}
PEOPLE: {people}"""
    return generate_json(brief, EmailDraft, system=SYSTEM)
