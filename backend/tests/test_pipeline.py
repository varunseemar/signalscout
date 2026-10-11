from datetime import date, timedelta
from types import SimpleNamespace

from signalscout.pipeline.enrich import _site_matches
from signalscout.pipeline.extract import looks_like_funding
from signalscout.pipeline.resolve import name_key, registered_domain, website_from_links
from signalscout.pipeline.score import score_company
from signalscout.pipeline.validate import clean_emails, clean_phones
from signalscout.scraper.text import html_to_text, outbound_links, url_hash


def test_name_key_normalises_suffixes_and_accents():
    assert name_key("Santé") == name_key("Sante") == "sante"
    assert name_key("Acme Labs, Inc.") == name_key("ACME") == "acme"
    assert name_key("Quartermaster AI") == "quartermaster"


def test_registered_domain():
    assert registered_domain("https://www.app.example.co.uk/path") == "example.co.uk"
    assert registered_domain("kaptaspace.com") == "kaptaspace.com"
    assert registered_domain(None) is None


def test_website_from_article_links():
    links = ["https://twitter.com/x", "https://www.kaptaspace.com/news", "https://bison.vc"]
    assert website_from_links("Kapta Space", links) == "https://kaptaspace.com"
    assert website_from_links("Abc", links) is None  # too short to match safely


def test_guessed_site_requires_name_and_topic_match():
    radar = "<title>Kapta Space | Radar satellites</title><h1>Steerable radar for orbit</h1>"
    assert _site_matches("Kapta Space", "Builds steerable radar sensors for satellites", radar)
    # Name in the title, but the page is about something unrelated
    shoes = "<title>True | Running shoes</title><h1>Shop running shoes</h1>"
    assert not _site_matches("True", "Fintech platform for payroll reconciliation", shoes)
    # Shares only its name with an unrelated business (yacht builder vs dental startup)
    yachts = "<title>Wally. 20 years ahead.</title><h1>Wally yachts</h1>"
    assert not _site_matches("Wally", "Wally provides subscription dental memberships", yachts)
    # Name only as a substring of another word
    assert not _site_matches("Ghost", "AI agents", "<title>Ghostwriter AI agents</title>")


def test_url_hash_is_canonical():
    assert url_hash("https://a.com/x?b=2&a=1") == url_hash("https://a.com/x?a=1&b=2")


def test_html_to_text_and_links():
    html = '<p>Hello <script>evil()</script>world</p><p>Visit <a href="https://acme.io">Acme</a> or <a href="https://twitter.com/a">tw</a></p>'
    assert html_to_text(html) == "Hello world\nVisit Acme or tw"
    assert outbound_links(html, "https://news.com/a") == ["https://acme.io"]


def test_funding_prefilter():
    assert looks_like_funding("Acme raises $12M Series A", "")
    assert not looks_like_funding("TechCrunch Disrupt tickets on sale", "Join us in San Francisco")


def test_phone_normalisation():
    phones = clean_phones({"(206) 555-0100", "+44 20 7946 0958", "123"}, "United States")
    assert {p["region"] for p in phones} <= {"US", "GB"}
    assert all(p["e164"].startswith("+") for p in phones)


def _company(**kw):
    base = dict(sector="AI / ML", hq_country="United States", hq_city="Austin", hiring=False,
                data_quality=80, emails=[{"confidence": "high"}])
    return SimpleNamespace(**{**base, **kw})


def _event(days_ago=1, amount=10e6, stage="Seed"):
    return SimpleNamespace(round_type=stage, amount_usd=amount, announced_on=date.today() - timedelta(days=days_ago))


def test_score_rewards_fit_and_freshness():
    fresh, _, reasons = score_company(_company(), _event(days_ago=1), {})
    stale, _, _ = score_company(_company(), _event(days_ago=60), {})
    off_icp, _, _ = score_company(_company(sector="Consumer", hq_country="France"), _event(days_ago=1), {})
    assert fresh > stale and fresh > off_icp
    assert reasons[0].startswith("Raised $10M Seed")
    assert 0 <= off_icp <= fresh <= 100


def test_clean_emails_strips_escapes_and_assets(monkeypatch):
    monkeypatch.setattr("signalscout.pipeline.validate.has_mx", lambda d: d == "acme.io")
    out = clean_emails({"u003esales@acme.io", "logo@2x.png", "jane@gmail.com", "info@acme.io"}, "acme.io")
    emails = {e["email"]: e for e in out}
    assert set(emails) == {"sales@acme.io", "info@acme.io", "jane@gmail.com"}
    assert emails["sales@acme.io"]["confidence"] == "high" and emails["sales@acme.io"]["type"] == "role"
    assert emails["jane@gmail.com"]["confidence"] == "low"
