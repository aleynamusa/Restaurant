"""Transparent, rule-based POS-need score (0-100).

Every point carries a reason so a salesperson can see *why* a lead ranks where it does, and
so the weights are easy to tune. The weights live in WEIGHTS below. Adjust them once you
have conversion data.

The idea behind it: a POS is bought once, around the moment a venue is set up or changes
hands. So timing (stage and recency) dominates. Ownership structure (chain vs independent)
and evidence of an existing system adjust from there.
"""
from __future__ import annotations

from datetime import date

from .models import (STAGE_ANNOUNCED, STAGE_OPENED, STAGE_PERMIT_APPLIED,
                     STAGE_PERMIT_GRANTED, Lead)

WEIGHTS = {
    "base": 20,
    "stage_permit_applied": 35,
    "stage_permit_granted": 30,
    "stage_announced": 30,
    "opened_30d": 22,
    "opened_90d": 12,
    "opened_older": 0,
    "osm_only_penalty": -8,
    "takeover": 10,
    "corroborated": 5,
    "cat_restaurant": 12,
    "cat_cafe": 8,
    "cat_bar": 7,
    "cat_fast_food": 5,
    "cat_unknown": 4,
    "terrace": 4,
    "integration_need": 4,
    "chain": -40,
    "has_pos": -22,
    "own_product": -100,
    "has_email": 5,
    "no_contact": -6,
}


def _days_since(iso: str, today: date) -> int | None:
    try:
        return (today - date.fromisoformat(iso[:10])).days
    except (ValueError, TypeError):
        return None


def score_lead(lead: Lead, today: date | None = None) -> None:
    today = today or date.today()
    W = WEIGHTS
    pts = W["base"]
    reasons: list[str] = []

    def add(n: int, why: str) -> None:
        nonlocal pts
        pts += n
        reasons.append(f"{'+' if n >= 0 else ''}{n} {why}")

    # Timing
    if lead.stage == STAGE_PERMIT_APPLIED:
        add(W["stage_permit_applied"], "pre-opening: horeca permit applied for, POS most likely not chosen yet")
    elif lead.stage == STAGE_PERMIT_GRANTED:
        add(W["stage_permit_granted"], "permit granted: opening is imminent, setup decisions happening now")
    elif lead.stage == STAGE_ANNOUNCED:
        add(W["stage_announced"], "opening announced but not yet open")
    elif lead.stage == STAGE_OPENED:
        d = _days_since(lead.opening_date or lead.event_date, today)
        if d is not None and d <= 30:
            add(W["opened_30d"], f"opened ~{d} days ago: still settling in, systems may be temporary")
        elif d is not None and d <= 90:
            add(W["opened_90d"], f"opened ~{d} days ago")
        else:
            add(W["opened_older"], "opening date unclear or older")
    if lead.extra.get("osm_only") and len({s["source"] for s in lead.sources}) == 1:
        add(W["osm_only_penalty"], "only seen on OpenStreetMap, so the opening date is unverified")

    if len({x["source"] for x in lead.sources}) >= 2:
        add(W["corroborated"], "confirmed by more than one independent source")
    if lead.is_takeover:
        add(W["takeover"], "new operator taking over a venue: inherited POS is often replaced")

    # Venue type
    cat_key = {"restaurant": "cat_restaurant", "cafe": "cat_cafe", "bar": "cat_bar",
               "fast_food": "cat_fast_food"}.get(lead.category, "cat_unknown")
    add(W[cat_key], f"venue type: {lead.category or 'unknown'}"
        + (" (table service: needs floor plan, courses, split bills)" if cat_key == "cat_restaurant" else ""))
    if lead.extra.get("terrace"):
        add(W["terrace"], "terrace permit: more covers, handheld ordering pays off")

    # Existing tech
    tech = lead.detected_tech
    if "pos:OWN_PRODUCT" in tech:
        add(W["own_product"], "already uses our product")
    elif any(t.startswith("pos:") or t.startswith("ordering:") for t in tech):
        names = ", ".join(t.split(":", 1)[1] for t in tech if t.startswith(("pos:", "ordering:")))
        add(W["has_pos"], f"website shows an existing POS/ordering system ({names})")
    elif any(t.startswith(("delivery:", "reservations:")) for t in tech):
        names = ", ".join(t.split(":", 1)[1] for t in tech if t.startswith(("delivery:", "reservations:")))
        add(W["integration_need"], f"uses {names}: needs a POS that integrates with it")

    # Ownership
    if lead.is_chain:
        add(W["chain"], "chain/franchise: POS is usually chosen centrally")

    # Actionability
    if lead.email:
        add(W["has_email"], "email address found")
    elif not lead.phone and not lead.website:
        add(W["no_contact"], "no contact details yet: needs manual lookup")

    lead.score = max(0, min(100, pts))
    lead.tier = "hot" if lead.score >= 70 else "warm" if lead.score >= 45 else "cold"
    lead.score_reasons = reasons
