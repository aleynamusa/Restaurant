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
    records, total = bekendmakingen.parse_sru((FIX / "sru_response.xml").read_text(encoding="utf-8"))
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
    els = json.loads((FIX / "overpass.json").read_text(encoding="utf-8"))["elements"]
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
    html = (tmp_path / "output" / "review.html").read_text(encoding="utf-8")
    assert "Vesper" in html and "mailto:" in html and "leaflet" in html
    # every demo lead gets a map position: OSM ones exact, permits geocoded, unknown addresses at the city centre
    by_name = {l.name: l for l in leads}
    assert all(l.lat is not None for l in leads)
    assert by_name["Vesper"].geo_precision == "exact"            # OSM position wins over the geocoded permit
    assert by_name["Lotus Ramen Bar"].geo_precision == "address"
    assert by_name["Wok&Go Express"].geo_precision == "city"
    assert '"lat": 51.9157' in html
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
                               parsed_output=EmailDraft(subject="A POS for Vesper", body="Hi there...", hook="permit"))

    monkeypatch.setattr(claude.client.beta.messages, "parse", fake_parse)
    lead = Lead(name="Vesper", city="Utrecht", stage="permit_applied", evidence=["Application for a hospitality operating permit"])
    pipeline.draft(lead, cfg, claude)
    assert lead.email_generator == "claude" and lead.email_subject == "A POS for Vesper"
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
    assert lead.email_generator == "template" and "has been granted" in lead.email_body


def test_geocoder_prefers_address_then_city(monkeypatch):
    from horeca_leads.geocode import Geocoder
    cfg = load_config(None)
    calls = []
    fetcher = Fetcher("t", fixtures={})
    monkeypatch.setattr(fetcher, "get", lambda url, params=None: calls.append(url) or
                        ('[{"lat": "52.38", "lon": "4.63"}]' if "Kerkstraat" in url else "[]"))
    geo = Geocoder(cfg, fetcher)
    a = Lead(name="A", city="Haarlem", address="Kerkstraat 9")
    b = Lead(name="B", city="Leiden", address="Nowhere 1")
    c = Lead(name="C", city="Atlantis")
    for l in (a, b, c):
        geo.locate(l)
    assert (a.lat, a.geo_precision) == (52.38, "address")
    assert b.geo_precision == "city" and round(b.lat, 1) == 52.2
    assert c.lat is None
    geo.locate(a)                      # already located: no second lookup
    assert len(calls) == 2 and "street=Kerkstraat" in calls[0]


def test_drafts_and_evidence_are_english():
    from horeca_leads.templates import template_email
    lead = Lead(name="New venue at Stratumseind 40", city="Eindhoven", address="Stratumseind 40",
                stage="permit_applied")
    subject, body = template_email(lead, load_config(None)["seller"])
    assert "your new venue on Stratumseind 40" in body and body.startswith("Hi there,")
    assert "John Doe" in body
    records, _ = bekendmakingen.parse_sru((FIX / "sru_response.xml").read_text(encoding="utf-8"))
    vesper = bekendmakingen.record_to_lead(records[0])
    assert vesper.evidence[0].startswith("Application for a hospitality operating permit, published in the Utrecht")


def test_expected_opening_reported_beats_estimate():
    reported = Lead(name="V", city="U", stage="permit_applied", event_date="2026-11-04", opening_date="2026-12-05")
    applied = Lead(name="A", city="U", stage="permit_applied", event_date="2026-11-08")
    granted = Lead(name="G", city="U", stage="permit_granted", event_date="2026-10-28")
    opened = Lead(name="O", city="U", stage="opened", event_date="2026-10-01")
    assert reported.expected_opening() == ("2026-12-05", "reported")
    assert applied.expected_opening() == ("2027-01-03", "estimated")   # ~8 weeks after the application
    assert granted.expected_opening() == ("2026-11-18", "estimated")   # ~3 weeks after the grant
    assert opened.expected_opening() == ("", "")


# ---------- prospect: website -> facts -> fit score -> email ----------
def _prospect(url, lang="en", claude=None):
    from horeca_leads import prospect as pros
    cfg = load_config(None)
    fetcher = Fetcher("t", fixtures=demo_fixtures())
    return pros.prospect(url, cfg, fetcher, claude, lang)


def test_prospect_rules_ranks_upcoming_opening_over_existing_pos():
    vesper = _prospect("https://vesper-utrecht.example.nl")
    coffee = _prospect("https://nooitgenoeg.example.nl")
    okra = _prospect("https://madameokra.example.nl", lang="nl")
    assert vesper.extracted_by == "rules" and vesper.facts["upcoming_opening"]["value"] == "yes"
    assert vesper.fit_tier == "strong" and vesper.fit_line.startswith("Strong fit (")
    assert coffee.facts["existing_pos"] == "Lightspeed" and coffee.fit_score < 40 and "Lightspeed" in coffee.fit_line
    assert okra.facts["reservation_platforms"] == ["Zenchef"] and okra.email_to == "hallo@madameokra.example.nl"
    assert okra.body.startswith("Hoi,") and "Thuisbezorgd en Zenchef" in okra.body and "John Doe" in okra.body
    assert "Winston POS" in okra.body


def test_prospect_claude_path_uses_structured_extraction(monkeypatch):
    from horeca_leads import prospect as pros
    cfg = load_config(None)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    claude = Claude(cfg)
    calls = []
    no = pros.Signal(value="no", evidence="")
    facts = pros.SiteFacts(
        name="Vesper", city="Utrecht", venue_type="restaurant", cuisine="Seasonal bistro",
        table_service=pros.Signal(value="yes", evidence="bistro"), online_ordering=no, ordering_platforms=[],
        reservations=no, reservation_platforms=[], existing_pos="",
        upcoming_opening=pros.Signal(value="yes", evidence="we open in December"), opening_date="2026-12",
        recently_opened=no, is_chain=False, hook="Opens on the Oudegracht in December")

    def fake_parse(**kw):
        calls.append(kw)
        out = facts if kw["output_format"] is pros.SiteFacts else EmailDraft(
            subject="Kassa klaar voor december?", body="Hoi, ...", hook="opening")
        return SimpleNamespace(stop_reason="end_turn", stop_details=None, parsed_output=out)

    monkeypatch.setattr(claude.client.beta.messages, "parse", fake_parse)
    p = _prospect("https://vesper-utrecht.example.nl", lang="nl", claude=claude)
    assert p.extracted_by == "claude" and p.email_generator == "claude" and p.fit_tier == "strong"
    extract, email = calls
    assert "Coming soon" in extract["messages"][0]["content"]          # the site text went to Claude
    assert "Write in Dutch" in email["system"] and "Opens on the Oudegracht" in email["messages"][0]["content"]
