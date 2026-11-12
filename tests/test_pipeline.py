from datetime import date
from pathlib import Path
from types import SimpleNamespace

from horeca_leads import pipeline, scoring
from horeca_leads.cli import DEMO_TODAY, demo_fixtures, main
from horeca_leads.config import load_config
from horeca_leads.enrich import detect_tech, pick_email
from horeca_leads.http import Fetcher
from horeca_leads.llm import Claude, EmailDraft
from horeca_leads.models import Lead
from horeca_leads.sources import bekendmakingen, osm
from horeca_leads.store import Store

FIX = Path(__file__).parent / "fixtures"


def test_sru_parsing_and_filtering():
    records, total = bekendmakingen.parse_sru((FIX / "sru_response.xml").read_text())
    assert total == 7 and len(records) == 7
    leads = [l for r in records if (l := bekendmakingen.record_to_lead(r))]
    names = {l.name for l in leads}
    # coffeeshop and manager-only change are excluded
    assert not any("Damstraat" in l.address or "Grote Markt" in l.address for l in leads)
    assert {"Vesper", "Lotus Ramen Bar", "De Kleine Ster", "Bistro Lune"} <= names
    ster = next(l for l in leads if l.name == "De Kleine Ster")
    assert ster.is_takeover and ster.stage == "permit_applied" and ster.city == "Haarlem"
    lotus = next(l for l in leads if l.name == "Lotus Ramen Bar")
    assert lotus.stage == "permit_granted" and lotus.address == "Witte de Withstraat 61"
    assert next(l for l in leads if l.name == "Bistro Lune").stage == "unknown"  # terrace-only


def test_osm_new_vs_edited():
    import json
    els = json.loads((FIX / "overpass.json").read_text())["elements"]
    today = DEMO_TODAY
    leads = [l for e in els if (l := osm.element_to_lead(e, date(2026, 9, 28), 2, today))]
    names = {l.name for l in leads}
    assert "Old Place Edited" not in names            # version 7: an edit, not a new place
    assert next(l for l in leads if l.name == "Vesper").stage == "announced"
    assert next(l for l in leads if l.name == "Five Guys").is_chain


def test_tech_and_email():
    assert detect_tech('<a href="https://order.lightspeed.app/x">') == ["pos:lightspeed"]
    assert "pos:OWN_PRODUCT" in detect_tech("powered by AcmeKassa", ["acmekassa"])
    assert pick_email(["logo@2x.png", "jan@gmail.com", "info@zaak.nl"], "https://www.zaak.nl") == "info@zaak.nl"


def test_scoring_orders_sensibly():
    pre = Lead(name="A", city="X", stage="permit_applied", category="restaurant", email="a@a.nl")
    chain = Lead(name="B", city="X", stage="permit_applied", category="restaurant", is_chain=True)
    has_pos = Lead(name="C", city="X", stage="opened", event_date="2026-11-01", detected_tech=["pos:tebi"])
    for l in (pre, chain, has_pos):
        scoring.score_lead(l, DEMO_TODAY)
    assert pre.score > has_pos.score and pre.score > chain.score
    assert pre.tier == "hot" and all(r[0] in "+-" for r in pre.score_reasons)


def test_demo_end_to_end(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert main(["run", "--demo", "--no-claude"]) == 0
    store = Store(tmp_path / "output" / "demo.db")
    leads = store.all()
    assert leads[0].name == "Vesper" and leads[0].email and leads[0].email_body
    assert len({l.id for l in leads}) == len(leads) == 10   # Vesper from permit + OSM merged
    html = (tmp_path / "output" / "review.html").read_text()
    assert "Vesper" in html and "mailto:" in html
    # statuses survive a re-run
    store.set_status(leads[0].id, "sent")
    assert main(["run", "--demo", "--no-claude"]) == 0
    assert Store(tmp_path / "output" / "demo.db").get(leads[0].id).status == "sent"


def test_claude_draft_path_uses_structured_output(monkeypatch):
    """Exercise the Claude code path without network: fake the SDK's parse() call."""
    cfg = load_config(None)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    claude = Claude(cfg)
    calls = {}

    def fake_parse(**kw):
        calls.update(kw)
        return SimpleNamespace(stop_reason="end_turn", stop_details=None,
                               parsed_output=EmailDraft(subject="Kassa voor Vesper", body="Hoi...", hook="permit"))

    monkeypatch.setattr(claude.client.beta.messages, "parse", fake_parse)
    lead = Lead(name="Vesper", city="Utrecht", stage="permit_applied", evidence=["aanvraag exploitatievergunning"])
    pipeline.draft(lead, cfg, claude)
    assert lead.email_generator == "claude" and lead.email_subject == "Kassa voor Vesper"
    assert calls["model"] == "claude-opus-5-5" and calls["output_format"] is EmailDraft
    assert calls["fallbacks"] == "default" and "Vesper" in calls["messages"][0]["content"]


def test_claude_failure_falls_back_to_template(monkeypatch):
    cfg = load_config(None)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    claude = Claude(cfg)
    monkeypatch.setattr(claude.client.beta.messages, "parse",
                        lambda **kw: SimpleNamespace(stop_reason="refusal", stop_details=None, parsed_output=None))
    lead = Lead(name="Vesper", city="Utrecht", stage="permit_granted")
    pipeline.draft(lead, cfg, claude)
    assert lead.email_generator == "template" and "verleend" in lead.email_body
