"""Config loading (TOML). Everything has a sensible default so the tool runs with no config."""
from __future__ import annotations

import copy
import tomllib
from pathlib import Path
from typing import Any

DEFAULTS: dict[str, Any] = {
    "general": {
        "lookback_days": 45,
        "db_path": "leads.db",
        "output_dir": "output",
        "user_agent": "horeca-leads/0.1 (B2B lead research)",
        "min_score_to_draft": 40,
    },
    "seller": {
        "company": "Winston POS",
        "sender_name": "John Doe",
        "sender_title": "Account Manager",
        "phone": "",
        "product_pitch": (
            "A POS system built for hospitality: table plan, ordering at the table on a handheld, "
            "QR ordering, integrations with Thuisbezorgd/Uber Eats and reservation systems, and "
            "built-in card payments. Up and running within 48 hours."
        ),
        "offer": "a free 20-minute demo, on site or online",
        # Used for Dutch emails (--lang nl). Replace both pitches with Winston POS's real selling points.
        "product_pitch_nl": (
            "Een kassasysteem voor horeca: tafelplattegrond, bestellen aan tafel via handheld, QR-bestellen, "
            "koppeling met Thuisbezorgd/Uber Eats en reserveringssystemen, en geïntegreerd pinnen. "
            "Binnen 48 uur operationeel."
        ),
        "offer_nl": "een vrijblijvende demo van 20 minuten, op locatie of online",
        "language": "en",       # en | nl (language of drafts written by Claude; templates are English)
        "tone": "informal",     # informal | formal
        # Names of your own product as they'd appear on a website. Prospects already
        # using it are excluded.
        "own_product_markers": ["winston pos", "winstonpos"],
    },
    "sources": {
        "bekendmakingen": {
            "enabled": True,
            "endpoint": "https://repository.overheid.nl/sru",
            # CQL against the officiële bekendmakingen SRU index. {since} is filled in.
            "query": (
                'c.product-area==officielepublicaties AND w.publicatienaam==Gemeenteblad '
                'AND dt.modified>={since} AND ('
                'dt.title any "exploitatievergunning horecavergunning alcoholwetvergunning '
                'drank- terrasvergunning horeca-exploitatievergunning")'
            ),
            "max_records": 500,
            "fetch_full_text": True,
        },
        "osm": {
            "enabled": True,
            "endpoint": "https://overpass-api.de/api/interpreter",
            "amenities": ["restaurant", "cafe", "fast_food", "bar", "pub", "ice_cream", "biergarten"],
            "max_version": 2,   # treat only freshly created map objects as "new"
        },
        "news": {
            "enabled": True,    # requires Claude for extraction
            "feeds": [
                "https://news.google.com/rss/search?q=%22nieuw+restaurant%22+when:30d&hl=nl&gl=NL&ceid=NL:nl",
                "https://news.google.com/rss/search?q=%22restaurant+opent%22+when:30d&hl=nl&gl=NL&ceid=NL:nl",
                "https://news.google.com/rss/search?q=%22opent+binnenkort%22+horeca+when:30d&hl=nl&gl=NL&ceid=NL:nl",
            ],
            "max_items": 60,
        },
        "csv": {"paths": []},
    },
    "enrich": {"fetch_websites": True, "timeout": 10},
    "geocode": {
        "enabled": True,        # look up addresses for the map (Nominatim); off = city centre only
        "endpoint": "https://nominatim.openstreetmap.org/search",
        "max_lookups": 300,     # per run; Nominatim allows 1 request/second
    },
    "claude": {
        "enabled": True,
        "model": "claude-opus-5-5",
        "email_effort": "medium",
        "extract_effort": "low",
        "use_fallbacks": True,
    },
    "scoring": {
        # Known Dutch / international chains: centrally procured POS, low odds.
        "chains": [
            "mcdonald", "burger king", "kfc", "domino", "new york pizza", "subway", "starbucks",
            "five guys", "dunkin", "febo", "kwalitaria", "smullers", "bram ladage", "la place",
            "vapiano", "wagamama", "happy italy", "loetje", "bagels & beans", "bagels and beans",
            "coffee company", "anne&max", "anne & max", "spare rib express", "doppio espresso",
            "van der valk", "fletcher", "salsa shop", "poke perfect", "poké perfect", "sumo",
            "jamie's", "hard rock", "taco bell", "popeyes", "wok to walk", "mangia", "dominos",
            "julia's", "bakker bart", "la cubanita", "the butcher", "humphrey's", "humphreys",
            "de beren", "tasty pancake", "bistro de pancake", "eazie", "ekoplaza", "bar basic",
            "manneken pis", "sushi time", "sumo sushi", "ristorante pizzeria da noi",
        ],
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(path: str | Path | None) -> dict[str, Any]:
    if path and Path(path).exists():
        with open(path, "rb") as f:
            return _deep_merge(DEFAULTS, tomllib.load(f))
    return copy.deepcopy(DEFAULTS)
