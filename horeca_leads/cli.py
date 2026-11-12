"""Command-line entry point.

  python -m horeca_leads run                 # live: fetch sources, score, draft, write review page
  python -m horeca_leads run --demo          # offline, on bundled sample data
  python -m horeca_leads review              # rebuild the review page/CSV from the database
  python -m horeca_leads mark <id> sent      # record a status by hand
  python -m horeca_leads import-decisions decisions.json   # sync statuses/edits back from the review page
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date
from pathlib import Path

from . import pipeline, report
from .config import load_config
from .http import Fetcher
from .llm import make_claude
from .store import Store

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
DEMO_TODAY = date(2026, 11, 12)


def demo_fixtures() -> dict[str, Path]:
    f = FIXTURES
    m = {
        "https://repository.overheid.nl/sru": f / "sru_response.xml",
        "https://overpass-api.de/": f / "overpass.json",
    }
    for p in (f / "notices").glob("*.xml"):
        m[f"https://zoek.officielebekendmakingen.nl/{p.stem}.xml"] = p
    sites = json.loads((f / "sites" / "index.json").read_text())
    for url, fname in sites.items():
        m[url] = f / "sites" / fname
    return m


def build_report(store: Store, cfg: dict) -> Path:
    out = Path(cfg["general"]["output_dir"])
    out.mkdir(parents=True, exist_ok=True)
    leads = store.all()
    report.write_html(leads, out / "review.html", cfg["seller"])
    report.write_csv(leads, out / "leads.csv")
    return out / "review.html"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="horeca_leads", description="Find new Dutch restaurants likely to need a POS.")
    ap.add_argument("--config", default="config.toml")
    ap.add_argument("-v", "--verbose", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="collect, score and draft")
    r.add_argument("--demo", action="store_true", help="use bundled sample data, no network")
    r.add_argument("--no-claude", action="store_true", help="use template emails, skip news extraction")
    r.add_argument("--redraft", action="store_true", help="regenerate drafts for leads still marked 'new'")
    r.add_argument("--limit", type=int, help="max emails to draft this run")
    r.add_argument("--days", type=int, help="override lookback window")
    sub.add_parser("review", help="rebuild review.html and leads.csv from the database")
    m = sub.add_parser("mark", help="set a lead's status")
    m.add_argument("lead_id")
    m.add_argument("status", choices=["new", "reviewed", "sent", "skipped"])
    i = sub.add_parser("import-decisions", help="import decisions.json exported from the review page")
    i.add_argument("path")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(message)s")
    cfg = load_config(args.config)

    if args.cmd == "run":
        today = date.today()
        if args.days:
            cfg["general"]["lookback_days"] = args.days
        if args.demo:
            today = DEMO_TODAY
            cfg["general"]["db_path"] = str(Path(cfg["general"]["output_dir"]) / "demo.db")
            cfg["sources"]["news"]["enabled"] = False
            cfg["sources"]["csv"]["paths"] = [str(FIXTURES / "kvk_sample.csv")]
            if cfg["seller"]["company"] == "YourPOS":
                cfg["seller"].update(company="Kassa Collectief", sender_name="Sanne de Vries")
        Path(cfg["general"]["output_dir"]).mkdir(parents=True, exist_ok=True)
        if args.no_claude:
            cfg["claude"]["enabled"] = False
        fetcher = Fetcher(cfg["general"]["user_agent"], cfg["enrich"]["timeout"],
                          fixtures=demo_fixtures() if args.demo else None)
        llm = make_claude(cfg)
        store = Store(cfg["general"]["db_path"])
        leads = pipeline.run(cfg, fetcher, llm, store, today=today, redraft=args.redraft, limit=args.limit)
        page = build_report(store, cfg)
        hot = sum(l.tier == "hot" for l in leads)
        print(f"\n{len(leads)} leads ({hot} hot). Review queue: {page.resolve()}")
        for l in leads[:10]:
            print(f"  {l.score:>3} {l.tier:<4} {l.name[:40]:<40} {l.city[:18]:<18} {l.stage}")
        return 0

    store = Store(cfg["general"]["db_path"])
    if args.cmd == "review":
        print(build_report(store, cfg).resolve())
    elif args.cmd == "mark":
        if not store.set_status(args.lead_id, args.status):
            print(f"no lead with id {args.lead_id}", file=sys.stderr)
            return 1
    elif args.cmd == "import-decisions":
        n = 0
        for d in json.loads(Path(args.path).read_text()):
            lead = store.get(d["id"])
            if not lead:
                continue
            lead.status = d.get("status", lead.status)
            lead.email = d.get("to") or lead.email
            lead.email_subject = d.get("subject") or lead.email_subject
            lead.email_body = d.get("body") or lead.email_body
            store.upsert(lead)
            store.set_status(lead.id, lead.status)
            n += 1
        print(f"updated {n} leads")
        build_report(store, cfg)
    return 0
