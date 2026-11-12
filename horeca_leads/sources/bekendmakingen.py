"""Municipal horeca permit notices from officielebekendmakingen.nl (Gemeenteblad).

Dutch municipalities must publish applications for and decisions on exploitatievergunningen,
drank- en horecavergunningen (Alcoholwet) and terrasvergunningen. An *application* for a new
address is the earliest public signal that a restaurant is coming, usually weeks before
it opens and before the owner has chosen a POS.

Access goes through the public SRU endpoint at repository.overheid.nl (no key needed).
"""
from __future__ import annotations

import html
import logging
import re
from datetime import date
from xml.etree import ElementTree as ET

from ..http import Fetcher
from ..models import (STAGE_PERMIT_APPLIED, STAGE_PERMIT_GRANTED, STAGE_UNKNOWN, Lead)

log = logging.getLogger(__name__)

HORECA_TERMS = re.compile(
    r"exploitatievergunning|horecavergunning|alcoholwet|drank-? en horeca|terrasvergunning|"
    r"horeca-?exploitatie|horecabedrijf|horecainrichting|horeca-?inrichting",
    re.I,
)
# Notices that mention horeca but are not about a restaurant opening.
EXCLUDE = re.compile(
    r"coffeeshop|seksinrichting|prostitutie|speelautomat|kansspel|evenement|"
    r"sluiting|intrekking|ingetrokken|bestuurlijke boete|last onder dwangsom|"
    r"aanwijzingsbesluit|beleidsregel|verordening|nachtvergunning|ontheffing sluitingstijd",
    re.I,
)
LEIDINGGEVENDE_ONLY = re.compile(r"wijziging (van )?(de )?leidinggevende|bijschrijving leidinggevende", re.I)
APPLIED = re.compile(r"aanvra(ag|gen)|ingediend|ontvangen|kennisgeving.*aanvraag", re.I)
GRANTED = re.compile(r"verleend|verlening|besluit|toegekend|afgegeven", re.I)
TAKEOVER = re.compile(r"overname|nieuwe exploitant|wijziging exploitant|andere exploitant|nieuwe eigenaar", re.I)
TERRACE = re.compile(r"terras", re.I)

STREET_SUFFIX = (
    r"straat|weg|laan|plein|gracht|kade|singel|markt|dijk|plantsoen|steeg|hof|pad|dreef|park|"
    r"baan|wal|haven|kanaal|boulevard|dam|brug|poort|veld|rijk|burgwal|ring|wijk|zijde|kwartier|"
    r"promenade|passage|erf|oord|hoek|straatje|lei|gang|einde|berg|bosch|weide|haag"
)
ADDRESS = re.compile(
    rf"\b((?:(?:[A-Z][\w'’.\-]*|de|van|der|den|het|'t|op|aan)\s){{0,4}}[A-Za-z'’.\-]*(?:{STREET_SUFFIX})\s+\d{{1,4}}(?:\s?[-‑]?\s?[A-Za-z]{{1,2}}\b|\s?-\s?\d{{1,4}}|\s?(?:bis|hs|huis|BG|bg)\b)?)",
)
# Fallbacks for streets without a recognisable suffix (Stratumseind, Oude Delft, Vismarkt...)
ADDRESS_CONTEXT = re.compile(
    r"(?:adres|aan de|aan het|gelegen aan|locatie|perceel)\s*:?\s*"
    r"((?:[A-Z][\w'’.\-]*\s(?:(?:de|van|der|den|het)\s)?){1,4}\d{1,4}(?:\s?[a-zA-Z]{1,2}\b)?)"
)
ADDRESS_TITLE_TAIL = re.compile(r",\s*((?:[A-Z][\w'’.\-]*\s(?:(?:de|van|der|den|het)\s)?){1,4}\d{1,4}[a-zA-Z]?)\s*$")
POSTCODE = re.compile(r"\b(\d{4}\s?[A-Z]{2})\b")
QUOTED_NAME = re.compile(r"[\"“‘'„]([^\"”’'“]{2,60})[\"”’']")
NAME_AFTER = re.compile(
    r"\b(?i:restaurant|eetcaf[ée]|caf[ée]|brasserie|bistro|lunchroom|pizzeria|bar|bakkerij|"
    r"koffiebar|grand caf[ée]|ijssalon|cocktailbar|wijnbar|snackbar|sushi)\s+"
    r"((?:[A-Z0-9][\w&'’\-]*)(?:\s+(?:de|het|van|der|en|&|[A-Z0-9][\w&'’\-]*)){0,4})"
)
NAME_COMPANY = re.compile(
    r"(?:verleend aan|aangevraagd door|aanvrager:?|ingediend door)\s+"
    r"((?:[A-Z0-9][\w&'’\-]*)(?:\s+(?:de|het|van|der|en|&|[A-Z0-9][\w&'’\-]*)){0,4}?)"
    r"(?:\s+(?:B\.V\.|V\.O\.F\.|VOF|BV|Holding))?(?=\s+(?:voor|aan|te|op)\b|,)"
)
NAME_HANDELSNAAM = re.compile(r"(?:handelsnaam|onder de naam|genaamd|met de naam)\s*:?\s*[\"“']?([^,.;\"”\n]{2,60})", re.I)

CATEGORY_HINTS = [
    ("restaurant", r"restaurant|bistro|brasserie|trattoria|ristorante|steakhouse|sushi|eethuis|grill|keuken"),
    ("cafe", r"eetcaf[ée]|grand caf[ée]|caf[ée]|lunchroom|koffie|coffee|bakery|bakkerij|tearoom|ontbijt"),
    ("bar", r"cocktail|wijnbar|bierbar|\bbar\b|kroeg|pub|biercaf"),
    ("fast_food", r"snackbar|cafetaria|friet|shoarma|kebab|pizzeria|poke|burger|afhaal"),
]


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _first(elem: ET.Element, name: str) -> str:
    for e in elem.iter():
        if _local(e.tag) == name and (e.text or "").strip():
            return e.text.strip()
    return ""


def _all(elem: ET.Element, name: str) -> list[str]:
    return [e.text.strip() for e in elem.iter() if _local(e.tag) == name and (e.text or "").strip()]


def parse_sru(xml_text: str) -> tuple[list[dict], int]:
    """Return (records, total_count). Namespace-agnostic, so small schema drifts don't break it."""
    root = ET.fromstring(xml_text)
    total = 0
    for e in root.iter():
        if _local(e.tag) == "numberOfRecords" and e.text:
            total = int(e.text)
            break
    records = []
    for rec in root.iter():
        if _local(rec.tag) != "record" or _first(rec, "identifier") == "":
            continue
        ident = _first(rec, "identifier")
        url = _first(rec, "preferredUrl") or _first(rec, "url") or f"https://zoek.officielebekendmakingen.nl/{ident}.html"
        records.append({
            "identifier": ident,
            "title": _first(rec, "title"),
            "creator": _first(rec, "creator"),         # municipality
            "modified": _first(rec, "modified") or _first(rec, "available") or _first(rec, "date"),
            "abstract": " ".join(_all(rec, "abstract") + _all(rec, "description")),
            "url": url,
            "xml_url": _first(rec, "itemUrl") or f"https://zoek.officielebekendmakingen.nl/{ident}.xml",
        })
    return records, total


def _strip_xml(text: str) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    return re.sub(r"\s+", " ", text).strip()


LEGAL_FORM = re.compile(r"\s+(?:B\.V\.|V\.O\.F\.|VOF|BV|C\.V\.|Holding)(?=[\s,.;]|$)")


def extract_name(text: str) -> str:
    text = LEGAL_FORM.sub("", text)
    for rx in (NAME_HANDELSNAAM, QUOTED_NAME, NAME_AFTER, NAME_COMPANY):
        m = rx.search(text)
        if m:
            name = m.group(1).strip(" .,:;")
            if rx is NAME_AFTER and m.group(0)[0].isupper():
                name = m.group(0).strip(" .,:;")  # "Bistro Lune" is the trade name; "restaurant Vesper" isn't
            # quoted strings are sometimes the permit type, not a name
            if not HORECA_TERMS.search(name) and len(name) >= 2 and not re.match(r"^(de|het|een)$", name, re.I):
                return name
    return ""


def permit_label(term: str) -> str:
    t = term.lower()
    if "terras" in t:
        return "terrasvergunning"
    if "alcohol" in t or "drank" in t:
        return "drank- en horecavergunning"
    return "exploitatievergunning"


def classify_category(text: str) -> str:
    for cat, rx in CATEGORY_HINTS:
        if re.search(rx, text, re.I):
            return cat
    return ""


def record_to_lead(rec: dict, full_text: str = "") -> Lead | None:
    rec = {k: html.unescape(v) if isinstance(v, str) else v for k, v in rec.items()}
    text = f"{rec['title']} {rec['abstract']} {full_text}"
    if not HORECA_TERMS.search(text) or EXCLUDE.search(rec["title"]):
        return None
    if LEIDINGGEVENDE_ONLY.search(rec["title"]) and not TAKEOVER.search(text):
        return None  # just a manager change at an existing venue

    head = f"{rec['title']} {rec['abstract']}"
    stage = STAGE_PERMIT_APPLIED if APPLIED.search(head) else (
        STAGE_PERMIT_GRANTED if GRANTED.search(head) else STAGE_PERMIT_APPLIED)
    terrace_only = bool(TERRACE.search(rec["title"])) and not re.search(
        r"exploitatie|alcohol|drank|horecavergunning", rec["title"], re.I)
    if terrace_only:
        stage = STAGE_UNKNOWN  # a terrace permit alone usually means an existing venue

    addr_m = (ADDRESS.search(rec["title"]) or ADDRESS_TITLE_TAIL.search(rec["title"])
              or ADDRESS.search(text) or ADDRESS_CONTEXT.search(text))
    address = re.sub(r"\s+", " ", addr_m.group(1)).strip() if addr_m else ""
    pc_m = POSTCODE.search(text)
    city = re.sub(r"^(gemeente|Gemeente)\s+", "", rec["creator"]).strip()
    name = extract_name(text)
    if not name and not address:
        return None

    permit_kind = HORECA_TERMS.search(rec["title"]) or HORECA_TERMS.search(text)
    kind = permit_label(permit_kind.group(0))
    stage_nl = "verleende" if stage == STAGE_PERMIT_GRANTED else "aanvraag"
    evidence = [f"{stage_nl} {kind} gepubliceerd in Gemeenteblad {city} op {rec['modified'][:10]}"]
    takeover = bool(TAKEOVER.search(text))
    if takeover:
        evidence.append("notice mentions a new operator / takeover")
    extra = {"permit_types": [kind]}
    if terrace_only:
        extra["terrace"] = True
        evidence.append("terrace permit only: probably an existing venue expanding")
    elif TERRACE.search(text):
        extra["terrace"] = True
        evidence.append("also applying for a terrace (terras)")

    return Lead(
        name=name or f"Horecazaak {address}",
        city=city,
        address=address,
        postcode=(pc_m.group(1).replace(" ", "") if pc_m else ""),
        category=classify_category(text),
        stage=stage,
        event_date=rec["modified"][:10],
        is_takeover=takeover,
        sources=[{"source": "bekendmakingen", "url": rec["url"], "title": rec["title"], "date": rec["modified"][:10]}],
        evidence=evidence,
        extra=extra,
    )


def fetch(cfg: dict, fetcher: Fetcher, since: date) -> list[Lead]:
    scfg = cfg["sources"]["bekendmakingen"]
    query = scfg["query"].format(since=since.isoformat())
    leads: list[Lead] = []
    start, page = 1, 100
    while start <= scfg["max_records"]:
        xml_text = fetcher.get(scfg["endpoint"], params={
            "query": query, "maximumRecords": page, "startRecord": start, "recordSchema": "gzd"})
        if not xml_text:
            break
        try:
            records, total = parse_sru(xml_text)
        except ET.ParseError as e:
            log.warning("bekendmakingen: bad XML: %s", e)
            break
        for rec in records:
            full = ""
            if scfg.get("fetch_full_text"):
                body = fetcher.get(rec["xml_url"])
                full = _strip_xml(body)[:6000] if body else ""
            lead = record_to_lead(rec, full)
            if lead:
                leads.append(lead)
        start += page
        if start > total or not records:
            break
    log.info("bekendmakingen: %d horeca leads", len(leads))
    return leads
