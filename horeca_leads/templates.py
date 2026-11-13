"""Deterministic fallback emails (English or Dutch), used when Claude isn't configured or a call fails."""
from __future__ import annotations

from .models import (STAGE_ANNOUNCED, STAGE_OPENED, STAGE_PERMIT_APPLIED,
                     STAGE_PERMIT_GRANTED, Lead, is_placeholder)


def _venue(lead: Lead, nl: bool) -> str:
    if is_placeholder(lead.name):
        if nl:
            return f"jullie nieuwe zaak aan de {lead.address}" if lead.address else "jullie nieuwe zaak"
        return f"your new venue on {lead.address}" if lead.address else "your new venue"
    return lead.name


def _platforms(lead: Lead, joiner: str = " and ") -> str:
    """Delivery/reservation tools seen on the website, e.g. 'Thuisbezorgd and Zenchef'."""
    names = [t.split(":", 1)[1] for t in lead.detected_tech if t.startswith(("delivery:", "reservations:", "ordering:"))]
    names = [n if n[:1].isupper() else n.title() for n in dict.fromkeys(names)][:3]
    return joiner.join([", ".join(names[:-1]), names[-1]]) if len(names) > 1 else (names[0] if names else "")


def template_email(lead: Lead, seller: dict) -> tuple[str, str]:
    if seller.get("language") == "nl":
        return _dutch(lead, seller)
    v = _venue(lead, False)
    where = f" in {lead.city}" if lead.city else ""
    if lead.stage in (STAGE_PERMIT_APPLIED, STAGE_PERMIT_GRANTED):
        verb = "granted" if lead.stage == STAGE_PERMIT_GRANTED else "requested"
        opener = (f"I saw in the municipal gazette that a hospitality permit has been {verb} for {v}{where}. "
                  "Congratulations, that means the opening is getting close.")
        problem = ("In the weeks before opening there's a lot to sort out at once. A till, card terminal and menu "
                   "that simply work on day one is one of them.")
        subject = f"POS sorted for the opening of {v[:30]}?"
    elif lead.stage == STAGE_ANNOUNCED:
        opener = f"I read that {v}{where} is opening soon. Congratulations!"
        problem = ("It pays to test your till and payments well before opening, so your team is comfortable "
                   "with them on day one.")
        subject = f"Your POS for the opening of {v[:35]}"
    elif lead.stage == STAGE_OPENED:
        opener = f"Congratulations on opening {v}{where}!"
        problem = ("After the first busy weeks, many new venues notice where their till falls short: splitting "
                   "bills, sending courses to the kitchen, or the link with delivery platforms.")
        subject = f"First weeks at {v[:35]}: how is the POS working?"
    else:
        opener = f"I came across {v}{where}."
        problem = "Many hospitality owners run into the same problems with their POS."
        subject = f"A POS for {v[:40]}"
        tools = _platforms(lead)
        if tools:
            opener = f"I came across {v}{where} and saw that you work with {tools}."
            problem = ("A till that connects to those directly means orders and bookings come in automatically, "
                       "without retyping them or juggling separate tablets.")
    if lead.is_takeover:
        problem = ("When you take over a venue you often inherit the previous owner's POS, along with its "
                   "contracts and limits. This is the moment to take a fresh look at it.")
    pitch = seller["product_pitch"].rstrip(".")
    pitch = pitch[:1].lower() + pitch[1:]
    body = (
        f"Hi there,\n\n{opener}\n\n{problem}\n\n"
        f"At {seller['company']} we help with exactly that: {pitch}.\n\n"
        f"Would you be up for {seller['offer']}?\n\n"
        f"Best regards,\n{seller['sender_name']}\n{seller['sender_title']}, {seller['company']}"
        + (f"\n{seller['phone']}" if seller.get("phone") else "")
        + "\n\nNot interested? Just reply 'no' and you won't hear from us again."
    )
    return subject, body


def _dutch(lead: Lead, seller: dict) -> tuple[str, str]:
    v = _venue(lead, True)
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
        tools = _platforms(lead, " en ")
        if tools:
            opener = f"Ik kwam {v}{where} tegen en zag dat jullie werken met {tools}."
            problem = ("Met een kassa die daar direct mee koppelt, komen bestellingen en reserveringen automatisch "
                       "binnen, zonder overtypen of losse tablets.")
    if lead.is_takeover:
        problem = ("Bij een overname neem je vaak het kassasysteem van de vorige eigenaar over, met de contracten "
                   "en beperkingen die daarbij horen. Dit is hét moment om dat opnieuw te bekijken.")
    pitch = seller.get("product_pitch_nl") or seller["product_pitch"]
    offer = seller.get("offer_nl") or seller["offer"]
    body = (
        f"Hoi,\n\n{opener}\n\n{problem}\n\n"
        f"Bij {seller['company']} helpen we daarmee. {pitch.rstrip('.')}.\n\n"
        f"Zin in {offer}?\n\n"
        f"Groet,\n{seller['sender_name']}\n{seller['sender_title']}, {seller['company']}"
        + (f"\n{seller['phone']}" if seller.get("phone") else "")
        + "\n\nGeen interesse? Antwoord met 'nee', dan hoor je niets meer van ons."
    )
    return subject, body
