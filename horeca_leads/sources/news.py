"""Opening announcements from news RSS feeds (Google News by default).

Headlines like "Nieuw Libanees restaurant opent in december aan de Grote Markt" are rich in
facts but unstructured, so Claude does the extraction. The source is skipped when Claude
is unavailable.
"""
from __future__ import annotations

import html
import logging
import re
from datetime import date
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

from ..http import Fetcher
from ..models import Lead

log = logging.getLogger(__name__)


def parse_rss(xml_text: str) -> list[dict]:
    items = []
    root = ET.fromstring(xml_text)
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        desc = re.sub(r"<[^>]+>", " ", html.unescape(it.findtext("description") or ""))
        pub = it.findtext("pubDate") or ""
        try:
            d = parsedate_to_datetime(pub).date().isoformat()
        except (TypeError, ValueError):
            d = ""
        items.append({"title": title, "description": re.sub(r"\s+", " ", desc).strip()[:600],
                      "url": (it.findtext("link") or "").strip(), "date": d})
    return items


def fetch(cfg: dict, fetcher: Fetcher, since: date, llm) -> list[Lead]:
    if llm is None:
        log.info("news: skipped (Claude not configured; it's needed to extract restaurants from articles)")
        return []
    scfg = cfg["sources"]["news"]
    items, seen = [], set()
    for feed in scfg["feeds"]:
        body = fetcher.get(feed)
        if not body:
            continue
        try:
            for it in parse_rss(body):
                key = it["title"].lower()
                if key not in seen and (not it["date"] or it["date"] >= since.isoformat()):
                    seen.add(key)
                    items.append(it)
        except ET.ParseError:
            log.warning("news: bad RSS from %s", feed)
    items = items[: scfg["max_items"]]
    if not items:
        return []
    leads = llm.extract_from_news(items)
    log.info("news: %d leads from %d articles", len(leads), len(items))
    return leads
