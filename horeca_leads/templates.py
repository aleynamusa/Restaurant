"""Deterministic fallback emails, used when Claude isn't configured or a call fails."""
from __future__ import annotations

from .models import (STAGE_ANNOUNCED, STAGE_OPENED, STAGE_PERMIT_APPLIED,
                     STAGE_PERMIT_GRANTED, Lead)


def _venue(lead: Lead) -> str:
    if lead.name.startswith("Horecazaak "):
        return f"jullie nieuwe zaak aan de {lead.address}" if lead.address else "jullie nieuwe zaak"
    return lead.name


def template_email(lead: Lead, seller: dict) -> tuple[str, str]:
    v = _venue(lead)
    where = f" in {lead.city}" if lead.city else ""
    if lead.stage in (STAGE_PERMIT_APPLIED, STAGE_PERMIT_GRANTED):
        verb = "verleend" if lead.stage == STAGE_PERMIT_GRANTED else "aangevraagd"
        opener = (f"Ik zag in het Gemeenteblad dat er een horecavergunning is {verb} voor {v}{where}. "
                  "Gefeliciteerd, dat betekent dat de opening dichtbij komt.")
        problem = ("In de weken voor de opening moet er veel tegelijk geregeld worden. Een kassa, pinautomaat en "
                   "menukaart die op dag één gewoon werken, is daar één van.")
        subject = f"Kassa geregeld voor de opening van {v[:30]}?"
    elif lead.stage == STAGE_ANNOUNCED:
        opener = f"Ik las dat {v}{where} binnenkort opent. Gefeliciteerd!"
        problem = "Het is slim om je kassa en betalingen ruim vóór de opening te testen, zodat je team er op dag één mee overweg kan."
        subject = f"Kassa voor de opening van {v[:35]}"
    elif lead.stage == STAGE_OPENED:
        opener = f"Gefeliciteerd met de opening van {v}{where}!"
        problem = ("Na de eerste drukke weken merken veel nieuwe zaken waar hun kassa tekortschiet: splitsen, "
                   "gangen doorsturen naar de keuken, of de koppeling met bezorgplatforms.")
        subject = f"Eerste weken {v[:35]}: hoe bevalt de kassa?"
    else:
        opener = f"Ik kwam {v}{where} tegen."
        problem = "Veel horecaondernemers lopen tegen dezelfde kassaproblemen aan."
        subject = f"Kassasysteem voor {v[:40]}"
    if lead.is_takeover:
        problem = ("Bij een overname neem je vaak het kassasysteem van de vorige eigenaar over, met de contracten "
                   "en beperkingen die daarbij horen. Dit is hét moment om dat opnieuw te bekijken.")
    pitch = seller["product_pitch"].rstrip(".")
    pitch = pitch[:1].lower() + pitch[1:]
    body = (
        f"Hoi,\n\n{opener}\n\n{problem}\n\n"
        f"Bij {seller['company']} helpen we daarmee: {pitch}.\n\n"
        f"Zin in {seller['offer']}?\n\n"
        f"Groet,\n{seller['sender_name']}\n{seller['sender_title']}, {seller['company']}"
        + (f"\n{seller['phone']}" if seller.get("phone") else "")
        + "\n\nGeen interesse? Antwoord met 'nee', dan hoor je niets meer van ons."
    )
    return subject, body
