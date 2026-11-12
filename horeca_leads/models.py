"""Core data model: one Lead per (restaurant, city)."""
from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Any

# Lifecycle stages, from earliest to latest.
STAGE_ANNOUNCED = "announced"          # news/social: "opening soon"
STAGE_PERMIT_APPLIED = "permit_applied"  # municipality published a permit application
STAGE_PERMIT_GRANTED = "permit_granted"  # permit granted, opening imminent
STAGE_OPENED = "opened"                # opened recently
STAGE_UNKNOWN = "unknown"

# Order of preference when two sightings of one place disagree.
STAGE_PRIORITY = [STAGE_PERMIT_APPLIED, STAGE_PERMIT_GRANTED, STAGE_ANNOUNCED, STAGE_OPENED, STAGE_UNKNOWN]
STAGES = [STAGE_ANNOUNCED, STAGE_PERMIT_APPLIED, STAGE_PERMIT_GRANTED, STAGE_OPENED, STAGE_UNKNOWN]


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    text = text.lower()
    text = re.sub(r"\b(restaurant|eetcafe|cafe|brasserie|bistro|bar|b\.?v\.?|v\.?o\.?f\.?)\b", " ", text)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def make_id(name: str, city: str, address: str = "") -> str:
    """Stable id. Prefer address-based identity, since permit notices often lack a trade name."""
    key = normalize(address) if address else normalize(name)
    raw = f"{key}|{normalize(city)}"
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


@dataclass
class Lead:
    name: str
    city: str = ""
    address: str = ""
    postcode: str = ""
    category: str = ""            # restaurant, cafe, fast_food, bar, ...
    stage: str = STAGE_UNKNOWN
    event_date: str = ""          # ISO date of the signal (publication / opening / mapping)
    opening_date: str = ""        # ISO date if known
    is_takeover: bool = False     # new operator on an existing premises
    is_chain: bool = False
    website: str = ""
    email: str = ""
    phone: str = ""
    sources: list[dict[str, str]] = field(default_factory=list)   # {"source","url","title","date"}
    evidence: list[str] = field(default_factory=list)              # short human-readable facts
    detected_tech: list[str] = field(default_factory=list)          # e.g. "pos:lightspeed", "reservations:zenchef"
    extra: dict[str, Any] = field(default_factory=dict)
    # filled later
    score: int = 0
    tier: str = ""
    score_reasons: list[str] = field(default_factory=list)
    email_subject: str = ""
    email_body: str = ""
    email_generator: str = ""     # "claude" | "template"
    status: str = "new"           # new | reviewed | sent | skipped
    id: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = make_id(self.name, self.city, self.address)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Lead":
        known = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**known)

    def merge(self, other: "Lead") -> None:
        """Merge a second sighting of the same place into this lead."""
        # Keep the most sales-relevant stage: an official permit beats a news/map sighting.
        if STAGE_PRIORITY.index(other.stage) < STAGE_PRIORITY.index(self.stage):
            self.stage = other.stage
        for attr in ("address", "postcode", "category", "website", "email", "phone", "opening_date"):
            if not getattr(self, attr) and getattr(other, attr):
                setattr(self, attr, getattr(other, attr))
        if self.name.startswith("Horecazaak ") and not other.name.startswith("Horecazaak "):
            self.name = other.name
        self.event_date = max(self.event_date, other.event_date)
        self.is_takeover = self.is_takeover or other.is_takeover
        self.is_chain = self.is_chain or other.is_chain
        seen = {s.get("url") for s in self.sources}
        self.sources += [s for s in other.sources if s.get("url") not in seen]
        self.evidence += [e for e in other.evidence if e not in self.evidence]
        self.detected_tech += [t for t in other.detected_tech if t not in self.detected_tech]
        for k, v in other.extra.items():
            self.extra.setdefault(k, v)
