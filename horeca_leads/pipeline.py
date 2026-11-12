"""Orchestration: collect, dedupe, enrich, score, draft, persist."""
from __future__ import annotations

import logging
from datetime import date, timedelta

import anthropic

from . import enrich, scoring
from .http import Fetcher
from .llm import Claude
from .models import Lead
from .sources import bekendmakingen, csv_import, news, osm
from .store import Store
from .templates import template_email

log = logging.getLogger(__name__)


def collect(cfg: dict, fetcher: Fetcher, llm: Claude | None, today: date) -> list[Lead]:
    since = today - timedelta(days=cfg["general"]["lookback_days"])
    s = cfg["sources"]
    found: list[Lead] = []
    if s["bekendmakingen"]["enabled"]:
        found += bekendmakingen.fetch(cfg, fetcher, since)
    if s["osm"]["enabled"]:
        found += osm.fetch(cfg, fetcher, since, today)
    if s["news"]["enabled"]:
        found += news.fetch(cfg, fetcher, since, llm)
    if s["csv"]["paths"]:
        found += csv_import.load(s["csv"]["paths"])
    return dedupe(found)


def dedupe(leads: list[Lead]) -> list[Lead]:
    """Merge on id (address+city), then on name+city for sightings without a common address."""
    from .models import make_id
    by_id: dict[str, Lead] = {}
    by_name: dict[str, str] = {}
    for l in leads:
        name_key = make_id(l.name, l.city)
        target = by_id.get(l.id) or (by_id.get(by_name[name_key]) if name_key in by_name else None)
        if target:
            target.merge(l)
        else:
            by_id[l.id] = l
            target = l
        if not target.name.startswith("Horecazaak "):
            by_name[make_id(target.name, target.city)] = target.id
    return list(by_id.values())


def run(cfg: dict, fetcher: Fetcher, llm: Claude | None, store: Store, today: date | None = None,
        redraft: bool = False, limit: int | None = None) -> list[Lead]:
    today = today or date.today()
    leads = collect(cfg, fetcher, llm, today)
    log.info("collected %d unique leads", len(leads))
    min_score = cfg["general"]["min_score_to_draft"]
    own = cfg["seller"]["own_product_markers"]
    out = []
    for lead in leads:
        prev = store.get(lead.id)
        if prev:
            prev.merge(lead)   # keep status + previous evidence, add new sightings
            lead = prev
        enrich.flag_chains(lead, cfg["scoring"]["chains"])
        if cfg["enrich"]["fetch_websites"] and not lead.extra.get("enriched"):
            enrich.enrich_lead(lead, fetcher, own)
            lead.extra["enriched"] = True
        scoring.score_lead(lead, today)
        out.append(lead)

    out.sort(key=lambda l: -l.score)
    drafted = 0
    for lead in out:
        needs = lead.score >= min_score and lead.status == "new" and (redraft or not lead.email_body)
        if needs and (limit is None or drafted < limit):
            draft(lead, cfg, llm)
            drafted += 1
        store.upsert(lead)
    log.info("drafted %d emails", drafted)
    return out


def draft(lead: Lead, cfg: dict, llm: Claude | None) -> None:
    if llm is not None:
        try:
            d = llm.draft_email(lead)
            lead.email_subject, lead.email_body, lead.email_generator = d.subject, d.body, "claude"
            return
        except (anthropic.APIError, RuntimeError) as e:
            log.warning("Claude draft failed for %s (%s); using template", lead.name, e)
    lead.email_subject, lead.email_body = template_email(lead, cfg["seller"])
    lead.email_generator = "template"
