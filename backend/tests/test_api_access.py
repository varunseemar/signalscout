import pytest
from fastapi.testclient import TestClient

from signalscout.api import main
from signalscout.config import Settings, get_settings

# No `with TestClient(...)`: startup (DB init) is not needed for these checks
client = TestClient(main.app)


@pytest.fixture
def admin_token(monkeypatch):
    monkeypatch.setattr(get_settings(), "admin_token", "s3cret")
    return "s3cret"


def test_open_mode_without_token(monkeypatch):
    monkeypatch.setattr(get_settings(), "admin_token", "")
    assert client.get("/api/config").json() == {"read_only": False, "is_admin": True}


def test_write_endpoints_require_admin(admin_token):
    assert client.get("/api/config").json() == {"read_only": True, "is_admin": False}
    assert client.post("/api/pipeline/run").status_code == 403
    assert client.patch("/api/leads/1", json={"status": "dismissed"}).status_code == 403
    icp = {"pitch": "x", "sectors": [], "countries": [], "stages": [], "min_amount_usd": 0, "max_amount_usd": 1}
    assert client.put("/api/icp", json=icp).status_code == 403
    assert client.get("/api/config", headers={"X-Admin-Token": admin_token}).json()["is_admin"] is True


def test_draft_rate_limit(monkeypatch):
    monkeypatch.setattr(get_settings(), "email_drafts_per_hour", 2)
    main._draft_log.clear()
    assert main._draft_allowed("1.2.3.4") and main._draft_allowed("1.2.3.4")
    assert not main._draft_allowed("1.2.3.4")
    assert main._draft_allowed("5.6.7.8")


@pytest.mark.parametrize("url", ["postgres://u:p@h/db", "postgresql://u:p@h/db?sslmode=require"])
def test_hosted_database_urls_get_psycopg_driver(url):
    assert Settings(database_url=url).database_url.startswith("postgresql+psycopg://u:p@h/db")
