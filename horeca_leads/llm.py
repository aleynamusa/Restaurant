"""Claude integration: extract leads from news items, and draft personalised first emails."""
from __future__ import annotations

import json
import logging
from typing import Literal, Optional

import anthropic
from pydantic import BaseModel, Field

from .models import STAGES, Lead, is_placeholder

log = logging.getLogger(__name__)

FALLBACK_BETA = "server-side-fallback-2026-07-01"


# ---------- schemas ----------
class ExtractedPlace(BaseModel):
    article_index: int = Field(description="index of the article this came from")
    name: str
    city: str
    address: str = ""
    category: Literal["restaurant", "cafe", "bar", "fast_food", "other"]
    stage: Literal["announced", "opened"]
    opening_date: str = Field("", description="ISO date YYYY-MM-DD if stated, else empty")
    is_takeover: bool = Field(description="new owner taking over an existing venue")
    is_chain: bool = Field(description="branch of a chain/franchise")
    fact: str = Field(description="one concrete fact from the article usable as an email hook, translated into English")


class Extraction(BaseModel):
    places: list[ExtractedPlace]


class EmailDraft(BaseModel):
    subject: str
    body: str
    hook: str = Field(description="which concrete fact the email is personalised on")


EXTRACT_SYSTEM = """You extract Dutch hospitality openings from news headlines and snippets for a B2B sales team.
Return only places in the Netherlands that are a single, specific restaurant, café, bar or food business
that has opened in the last ~3 months or is going to open. Skip closures, reviews of long-running places,
festivals, events, chains announcing many branches at once without one specific location, and anything outside
the Netherlands. Use only facts present in the text: never guess an address or date. If no place qualifies, return
an empty list."""


def _email_system(seller: dict) -> str:
    dutch = seller["language"] == "nl"
    lang = "Dutch" if dutch else "English"
    if dutch:
        tone = "informal Dutch 'je/jij' as is normal among Dutch hospitality entrepreneurs" \
            if seller["tone"] == "informal" else "formal Dutch 'u'"
    else:
        tone = "friendly and relaxed" if seller["tone"] == "informal" else "friendly, professional"
    greeting = '"Hoi," / "Beste ondernemer,"' if dutch else '"Hi there," / "Hello,"'
    optout = "'nee'" if dutch else "'no'"
    return f"""You write the first cold email from a POS salesperson to the owner of a restaurant
that has just opened or is about to open in the Netherlands. A human reviews and sends every email.

Seller: {seller['sender_name']}, {seller['sender_title']} at {seller['company']}.
What we sell: {seller['product_pitch']}
Offer / call to action: {seller['offer']}.

Write in {lang}, {tone}. Rules:
- 70 to 120 words in the body. Short paragraphs. Plain text, no markdown, no emoji.
- Open with ONE specific, verifiable fact about this venue taken from the lead facts (the permit, the opening,
  the street, the type of kitchen, the terrace, the takeover). Never invent facts, names, dates or numbers that are not
  in the lead facts. If the owner's name is unknown, use a neutral greeting ({greeting}). Never use or guess a
  real person's name; if an example person is ever needed, use "John Doe" or "Jane Doe".
- Connect that fact to one concrete problem a POS solves for a venue of exactly this type and stage
  (e.g. pre-opening: get the till, card terminal and menu set up before day one; takeover: replacing an
  inherited system; terrace: handheld ordering; delivery platforms: orders straight into the kitchen).
- If the lead shows they already use reservation or delivery tools, mention that we integrate with them.
  If they already have a POS, take a "worth comparing" angle and don't claim theirs is bad.
- One clear, low-friction call to action. No pressure tactics, no superlatives, no fake urgency.
- End with the signature (name, title, company{', phone' if seller.get('phone') else ''}), then one short line saying they
  can reply {optout} and won't hear from us again.
- Subject: under 60 characters, specific to the venue, not salesy."""


class Claude:
    def __init__(self, cfg: dict):
        c = cfg["claude"]
        self.client = anthropic.Anthropic()
        self.model = c["model"]
        self.email_effort = c["email_effort"]
        self.extract_effort = c["extract_effort"]
        self.use_fallbacks = c["use_fallbacks"]
        self.seller = cfg["seller"]

    def _parse(self, *, system: str, user: str, schema, effort: str, max_tokens: int = 16000):
        kwargs = dict(model=self.model, max_tokens=max_tokens, system=system,
                      messages=[{"role": "user", "content": user}],
                      output_format=schema, output_config={"effort": effort})
        if self.use_fallbacks:
            # On a policy decline the API retries the same request on a fallback model.
            kwargs.update(betas=[FALLBACK_BETA], fallbacks="default")
        resp = self.client.beta.messages.parse(**kwargs)
        if resp.stop_reason == "refusal":
            raise RuntimeError(f"Claude declined: {getattr(resp.stop_details, 'category', None)}")
        if resp.stop_reason == "max_tokens":
            raise RuntimeError("Claude response hit max_tokens")
        return resp.parsed_output

    # ---------- news extraction ----------
    def extract_from_news(self, items: list[dict]) -> list[Lead]:
        listing = "\n".join(
            f"[{i}] {it['date']} | {it['title']} | {it['description']}" for i, it in enumerate(items))
        try:
            out: Extraction = self._parse(system=EXTRACT_SYSTEM, user=f"Articles:\n{listing}",
                                          schema=Extraction, effort=self.extract_effort)
        except (anthropic.APIError, RuntimeError) as e:
            log.warning("news extraction failed: %s", e)
            return []
        leads = []
        for p in out.places:
            if not (0 <= p.article_index < len(items)) or not p.name or not p.city:
                continue
            it = items[p.article_index]
            leads.append(Lead(
                name=p.name, city=p.city, address=p.address,
                category="" if p.category == "other" else p.category,
                stage=p.stage if p.stage in STAGES else "unknown",
                event_date=p.opening_date or it["date"], opening_date=p.opening_date,
                is_takeover=p.is_takeover, is_chain=p.is_chain,
                sources=[{"source": "news", "url": it["url"], "title": it["title"], "date": it["date"]}],
                evidence=[f"news: {p.fact}"],
            ))
        return leads

    # ---------- email drafting ----------
    def draft_email(self, lead: Lead) -> EmailDraft:
        facts = {
            "name": "(trade name unknown)" if is_placeholder(lead.name) else lead.name,
            "city": lead.city, "address": lead.address, "category": lead.category or "unknown",
            "stage": lead.stage, "opening_date": lead.opening_date, "is_takeover": lead.is_takeover,
            "facts": lead.evidence,
            "tech_on_website": lead.detected_tech,
            "website_summary": lead.extra.get("site_summary", ""),
            "cuisine": lead.extra.get("cuisine", ""),
            "terrace": bool(lead.extra.get("terrace")),
            "why_we_think_they_need_a_pos": lead.score_reasons,
        }
        return self._parse(system=_email_system(self.seller),
                           user="Lead facts (JSON):\n" + json.dumps(facts, ensure_ascii=False, indent=2),
                           schema=EmailDraft, effort=self.email_effort)


def make_claude(cfg: dict) -> Optional[Claude]:
    if not cfg["claude"]["enabled"]:
        return None
    try:
        return Claude(cfg)
    except anthropic.AnthropicError as e:  # e.g. no credentials configured
        log.warning("Claude unavailable (%s); using templates and skipping news extraction", e)
        return None
