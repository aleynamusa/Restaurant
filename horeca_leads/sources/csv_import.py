"""Import leads from CSV, e.g. a KvK (Chamber of Commerce) export of new SBI 56101 registrations,
a list from a field rep, or a purchased list.

Recognised columns (case-insensitive; Dutch names work too): name/naam/handelsnaam, city/plaats,
address/adres, postcode, category, stage, date/datum/registratiedatum, opening_date, website,
email, phone/telefoon, note/notitie, sbi.
"""
from __future__ import annotations

import csv
import logging
from pathlib import Path

from ..models import STAGES, STAGE_OPENED, STAGE_UNKNOWN, Lead

log = logging.getLogger(__name__)

ALIASES = {
    "name": ["name", "naam", "handelsnaam", "bedrijfsnaam"],
    "city": ["city", "plaats", "vestigingsplaats", "woonplaats", "gemeente"],
    "address": ["address", "adres", "straat", "vestigingsadres"],
    "postcode": ["postcode", "zip"],
    "category": ["category", "categorie", "type"],
    "stage": ["stage", "fase"],
    "date": ["date", "datum", "registratiedatum", "inschrijvingsdatum", "datum_oprichting"],
    "opening_date": ["opening_date", "openingsdatum"],
    "website": ["website", "url", "site"],
    "email": ["email", "e-mail", "mail"],
    "phone": ["phone", "telefoon", "tel"],
    "note": ["note", "notitie", "opmerking"],
    "sbi": ["sbi", "sbi_code", "sbi-code"],
}


def _get(row: dict, field: str) -> str:
    lower = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
    for alias in ALIASES[field]:
        if lower.get(alias):
            return lower[alias]
    return ""


def load(paths: list[str]) -> list[Lead]:
    leads = []
    for p in paths:
        path = Path(p)
        if not path.exists():
            log.warning("csv: %s not found", p)
            continue
        with path.open(newline="", encoding="utf-8-sig") as f:
            sample = f.read(2048)
            f.seek(0)
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t") if sample else csv.excel
            for row in csv.DictReader(f, dialect=dialect):
                name = _get(row, "name")
                if not name:
                    continue
                stage = _get(row, "stage")
                sbi = _get(row, "sbi")
                evidence = []
                if _get(row, "date"):
                    evidence.append(f"Registered/listed on {_get(row, 'date')} ({path.name})")
                if sbi:
                    evidence.append(f"SBI code {sbi}")
                if _get(row, "note"):
                    evidence.append(_get(row, "note"))
                leads.append(Lead(
                    name=name, city=_get(row, "city"), address=_get(row, "address"),
                    postcode=_get(row, "postcode").replace(" ", ""),
                    category=_get(row, "category") or ("restaurant" if sbi.startswith("5610") else ""),
                    stage=stage if stage in STAGES else (STAGE_OPENED if _get(row, "date") else STAGE_UNKNOWN),
                    event_date=_get(row, "date")[:10], opening_date=_get(row, "opening_date")[:10],
                    website=_get(row, "website"), email=_get(row, "email"), phone=_get(row, "phone"),
                    sources=[{"source": "csv", "url": f"file:{path.name}", "title": path.name, "date": _get(row, "date")[:10]}],
                    evidence=evidence,
                ))
    log.info("csv: %d leads", len(leads))
    return leads
