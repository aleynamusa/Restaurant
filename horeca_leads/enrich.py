"""Website enrichment: contact details plus a fingerprint of the tech the place already runs.

The fingerprints matter for scoring. A site embedding Lightspeed or Tebi ordering already has
a POS. A reservation or delivery widget only means the place is tech-savvy and will need
integrations.
"""
from __future__ import annotations

import logging
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .http import Fetcher
from .models import Lead

log = logging.getLogger(__name__)

# marker substrings (lowercase) found in HTML -> tech label
FINGERPRINTS: dict[str, list[str]] = {
    "pos:lightspeed": ["lightspeedhq", "lightspeed restaurant", "order.lightspeed", "ikentoo", "lsk.lightspeed"],
    "pos:untill": ["untill", "unti11"],
    "pos:tebi": ["tebi.co", "tebi.app", "order.tebi"],
    "pos:square": ["squareup.com", "square.site", "squarespace-cdn.com/square"],
    "pos:sumup": ["sumup.com", "sumup.link", "sumup.store"],
    "pos:zettle": ["izettle", "zettle.com"],
    "pos:orderbird": ["orderbird"],
    "pos:mplus": ["mpluskassa", "mplus-kassa"],
    "pos:gastrofix": ["gastrofix"],
    "pos:hospitality_systems": ["hospitality-systems", "hosp.systems"],
    "pos:trivec": ["trivec"],
    "ordering:qr": ["qr-bestellen", "orderbuddy", "mr.order", "mrorder", "yoursmenu", "menutiger", "orderyoyo", "deliverect"],
    "reservations:formitable": ["formitable"],
    "reservations:zenchef": ["zenchef"],
    "reservations:resengo": ["resengo"],
    "reservations:thefork": ["thefork", "lafourchette"],
    "reservations:opentable": ["opentable"],
    "reservations:tablebooker": ["tablebooker"],
    "reservations:guestplan": ["guestplan"],
    "delivery:thuisbezorgd": ["thuisbezorgd", "takeaway.com", "just eat"],
    "delivery:ubereats": ["ubereats", "uber eats"],
    "delivery:deliveroo": ["deliveroo"],
}

EMAIL_RX = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
PHONE_RX = re.compile(r"(?:\+31|0031|\b0)[\s\-]?(?:\(0\)[\s\-]?)?\d(?:[\s\-]?\d){8}\b")
BAD_EMAIL = re.compile(r"\.(png|jpe?g|gif|svg|webp)$|sentry|wixpress|@example\.|@2x|@domain\.|@(?:email|yourdomain|jouwdomein)\.", re.I)
COMING_SOON = re.compile(r"binnenkort|coming soon|opent (op|in)|opening (op|in)|grand opening|soft opening", re.I)


def detect_tech(html: str, own_markers: list[str] | None = None) -> list[str]:
    low = html.lower()
    found = [label for label, markers in FINGERPRINTS.items() if any(m in low for m in markers)]
    for m in own_markers or []:
        if m and m.lower() in low:
            found.append("pos:OWN_PRODUCT")
            break
    return found


def pick_email(emails: list[str], website: str) -> str:
    domain = urlparse(website).netloc.removeprefix("www.")
    cleaned = []
    for e in emails:
        e = e.strip(".").lower()
        if BAD_EMAIL.search(e) or e in cleaned:
            continue
        cleaned.append(e)
    if not cleaned:
        return ""
    # prefer an address on the restaurant's own domain, and generic inboxes owners read
    def rank(e: str) -> tuple[int, int]:
        on_domain = 0 if domain and e.endswith("@" + domain) else 1
        generic = 0 if re.match(r"^(info|hallo|hello|contact|reserveringen|eten|mail)@", e) else 1
        return (on_domain, generic)
    return sorted(cleaned, key=rank)[0]


def enrich_lead(lead: Lead, fetcher: Fetcher, own_markers: list[str] | None = None) -> None:
    if not lead.website:
        return
    url = lead.website if lead.website.startswith("http") else "https://" + lead.website
    html = fetcher.get(url)
    if not html:
        lead.extra["website_unreachable"] = True
        return
    pages = [html]
    soup = BeautifulSoup(html, "lxml")
    # follow one contact-ish link for the email address
    for a in soup.find_all("a", href=True):
        if re.search(r"contact|over-ons|about|reserv", a["href"], re.I) and not a["href"].startswith("mailto:"):
            sub = fetcher.get(urljoin(url, a["href"]))
            if sub:
                pages.append(sub)
            break
    blob = "\n".join(pages)
    tech = detect_tech(blob, own_markers)
    lead.detected_tech += [t for t in tech if t not in lead.detected_tech]

    mailtos = re.findall(r"mailto:([^\"'?>\s]+)", blob, re.I)
    if not lead.email:
        lead.email = pick_email(mailtos + EMAIL_RX.findall(BeautifulSoup(blob, "lxml").get_text(" ")), url)
    if not lead.phone:
        m = PHONE_RX.search(BeautifulSoup(blob, "lxml").get_text(" "))
        if m:
            lead.phone = m.group(0)
    text = soup.get_text(" ", strip=True)
    if COMING_SOON.search(text):
        lead.evidence.append("Website says the restaurant is opening soon")
        lead.extra["site_coming_soon"] = True
    title = soup.title.get_text(strip=True) if soup.title else ""
    desc = soup.find("meta", attrs={"name": "description"})
    lead.extra["site_summary"] = " | ".join(x for x in [title, desc.get("content", "") if desc else ""] if x)[:300]


def flag_chains(lead: Lead, chains: list[str]) -> None:
    n = lead.name.lower()
    for c in chains:
        if re.search(rf"(^|\W){re.escape(c)}", n):
            lead.is_chain = True
            if f"Name matches chain '{c}'" not in lead.evidence:
                lead.evidence.append(f"Name matches chain '{c}'")
            return
