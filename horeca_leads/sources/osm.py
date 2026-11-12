"""Newly mapped food & drink places in the Netherlands from OpenStreetMap (Overpass API).

Two signals:
  * objects created recently (low version number, recent timestamp): often a place that
    just opened. This is a weaker signal, since a mapper may have added an old place.
  * objects with an explicit `opening_date` tag in the recent past or the future.
"""
from __future__ import annotations

import json
import logging
from datetime import date, timedelta

from ..http import Fetcher
from ..models import STAGE_ANNOUNCED, STAGE_OPENED, Lead

log = logging.getLogger(__name__)

CATEGORY = {"restaurant": "restaurant", "cafe": "cafe", "fast_food": "fast_food", "bar": "bar",
            "pub": "bar", "biergarten": "bar", "ice_cream": "fast_food", "food_court": "fast_food"}


def build_query(amenities: list[str], since: date) -> str:
    rx = "^(" + "|".join(amenities) + ")$"
    return f"""
[out:json][timeout:180];
area["ISO3166-1"="NL"][admin_level=2]->.nl;
(
  nwr["amenity"~"{rx}"]["name"](area.nl)(newer:"{since.isoformat()}T00:00:00Z");
  nwr["amenity"~"{rx}"]["opening_date"](area.nl);
);
out center meta;
""".strip()


def element_to_lead(el: dict, since: date, max_version: int, today: date) -> Lead | None:
    tags = el.get("tags", {})
    name = tags.get("name")
    if not name:
        return None
    ts = (el.get("timestamp") or "")[:10]
    opening = tags.get("opening_date", "")[:10]
    stage, evidence = None, []
    if opening:
        try:
            od = date.fromisoformat(opening if len(opening) == 10 else opening + "-01")
        except ValueError:
            od = None
        if od and od > today:
            stage = STAGE_ANNOUNCED
            evidence.append(f"OpenStreetMap lists opening date {opening}")
        elif od and od >= today - timedelta(days=120):
            stage = STAGE_OPENED
            evidence.append(f"OpenStreetMap lists opening date {opening}")
    if stage is None and el.get("version", 99) <= max_version and ts >= since.isoformat():
        stage = STAGE_OPENED
        evidence.append(f"first added to OpenStreetMap on {ts} (suggests a recent opening, not confirmed)")
    if stage is None:
        return None
    street = tags.get("addr:street", "")
    hn = tags.get("addr:housenumber", "")
    lead = Lead(
        name=name,
        city=tags.get("addr:city", ""),
        address=f"{street} {hn}".strip(),
        postcode=tags.get("addr:postcode", "").replace(" ", ""),
        category=CATEGORY.get(tags.get("amenity", ""), ""),
        stage=stage,
        event_date=opening if stage == STAGE_ANNOUNCED else (opening or ts),
        opening_date=opening,
        is_chain=bool(tags.get("brand") or tags.get("brand:wikidata")),
        website=tags.get("website") or tags.get("contact:website", ""),
        email=tags.get("email") or tags.get("contact:email", ""),
        phone=tags.get("phone") or tags.get("contact:phone", ""),
        sources=[{"source": "osm", "url": f"https://www.openstreetmap.org/{el['type']}/{el['id']}",
                  "title": f"OSM {tags.get('amenity')}: {name}", "date": ts}],
        evidence=evidence,
        extra={"cuisine": tags.get("cuisine", ""), "osm_only": True},
    )
    if tags.get("brand"):
        lead.evidence.append(f"tagged as part of brand '{tags['brand']}'")
    return lead


def fetch(cfg: dict, fetcher: Fetcher, since: date, today: date | None = None) -> list[Lead]:
    today = today or date.today()
    scfg = cfg["sources"]["osm"]
    body = fetcher.post(scfg["endpoint"], data={"data": build_query(scfg["amenities"], since)})
    if not body:
        return []
    try:
        elements = json.loads(body).get("elements", [])
    except json.JSONDecodeError:
        log.warning("osm: response was not JSON")
        return []
    leads = [l for el in elements if (l := element_to_lead(el, since, scfg["max_version"], today))]
    log.info("osm: %d candidate places", len(leads))
    return leads
