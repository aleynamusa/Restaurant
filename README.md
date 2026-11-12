# horeca-leads

Finds restaurants in the Netherlands that recently opened or are about to open. It scores how likely each one is to need a new POS (kassasysteem) and drafts a personalised first email. A salesperson opens one page, reads why each lead ranks where it does, tweaks the draft and clicks **Open in email app**.

```
sources ──► dedupe ──► enrich website ──► score ──► draft email ──► review.html / leads.csv
                                                                     (SQLite keeps status between runs)
```

## Quick start

```bash
pip install -r requirements.txt
python -m horeca_leads run --demo --no-claude     # offline, bundled sample data
open output/review.html
```

For live data:

```bash
cp config.example.toml config.toml                 # set your company, name, pitch
export ANTHROPIC_API_KEY=...                       # optional; without it, template emails are used
python -m horeca_leads run
```

Run it daily or weekly (cron, or a scheduled CI job). Leads are deduplicated across runs. Anything marked sent or skipped stays that way, and new sightings of a known place are merged into the existing lead.

## Where leads come from

| Source | Signal | Strength |
|---|---|---|
| **Gemeenteblad** via officielebekendmakingen.nl (public SRU API, no key) | Applications for and grants of an *exploitatievergunning* or *drank- en horecavergunning* at an address. Usually published weeks before opening, before a POS has been chosen. | Strongest |
| **OpenStreetMap** (Overpass API) | Food/drink places with an `opening_date` tag, or newly created on the map in the lookback window. Often includes website, email and phone. | Medium; "new on the map" isn't proof of a new opening, so it's penalised unless something else confirms it |
| **News RSS** (Google News queries, configurable) | "Restaurant X opent in december aan de Y". Claude extracts the place, city, stage and one usable fact. | Medium; needs Claude |
| **CSV import** | KvK export of new SBI 5610x registrations, purchased lists, or a field rep's notes. Dutch or English column names work. | Depends on the list |

Filtered out: coffeeshops, events, closures and enforcement notices, manager-only changes (*wijziging leidinggevende*), and terrace permits for existing venues. Terrace-only permits are kept but scored low.

## How the score works (0–100)

The score is rule-based and every point comes with a reason that's shown to the salesperson. Weights are in `horeca_leads/scoring.py` (`WEIGHTS`).

* **Timing (biggest factor):** permit applied +35 · permit granted +30 · announced +30 · opened ≤30 days ago +22 · ≤90 days ago +12
* **Takeover / new operator:** +10. Inherited systems often get replaced.
* **Venue type:** restaurant +12 · café +8 · bar +7 · fast food +5
* **Terrace:** +4 · **Uses delivery or reservation platforms** (Thuisbezorgd, Zenchef, Formitable…): +4, since they need integrations
* **Existing POS seen on the website** (Lightspeed, Untill, Tebi, Square, SumUp, Zettle, orderbird…): −22
* **Already uses your product:** −100 (set `own_product_markers`)
* **Chain/franchise** (name list + OSM `brand` tag): −40
* **Confirmed by 2+ sources:** +5 · **Email found:** +5 · **No contact details:** −6

Tiers: **hot** ≥70, **warm** 45–69, **cold** <45. Emails are drafted from `min_score_to_draft` (default 40) upward. Once you have reply and conversion data, tune `WEIGHTS` against it.

## Email drafting

With Claude available (`claude-opus-5-5`, structured output), each draft:
* opens with one verifiable fact about the venue (the permit, the street, the takeover, the terrace) and is told never to invent facts;
* ties that fact to one POS problem for a venue at that stage;
* mentions integrations if the site shows Zenchef or Thuisbezorgd, and takes a "worth comparing" angle if they already have a POS;
* is in Dutch, uses *je* by default (configurable), is 70–120 words, has one CTA, and includes an opt-out line.

Server-side refusal fallbacks are on (`use_fallbacks`). If a call fails, that lead gets a deterministic Dutch template instead, so nothing blocks. The draft's origin (claude/template) is shown on each card.

## Review workflow

`output/review.html` is a single self-contained file. You can share it or open it locally.
* Filter: To do / Hot only / All / Sent-skipped
* Edit the To, subject and body inline. Edits are saved in your browser.
* **Open in email app** opens a prefilled `mailto:` draft. **Mark sent** / **Skip** files the lead away.
* **Export decisions** downloads `decisions.json`. Run `python -m horeca_leads import-decisions decisions.json` to write statuses and edits back to the database, so the next run doesn't re-surface them.

Other commands: `review` (rebuild page + CSV), `mark <id> sent`, `run --limit 20`, `run --redraft`, `run --days 14`.

## Notes and limits

* **Unverified against live APIs.** The Gemeenteblad SRU query (index names in `config.toml → sources.bekendmakingen.query`) and the Overpass query were built against their documented formats, but the build environment had no access to those hosts. Do a first live run with `-v` and check the counts. The parsers are namespace-agnostic, and the query is configurable in case an index name differs.
* Permit notices often lack a trade name. Those leads show as "Horecazaak <address>" and are drafted around the address. Contact details then usually need a manual lookup (the card says so).
* **Cold email rules (Telecommunicatiewet / AVG):** B2B email to a legal entity's generic address (info@) is generally allowed with an opt-out. Sole proprietorships (eenmanszaak/VOF) are treated as natural persons, which needs more care. Every draft includes an opt-out line, but check your own policy. The tool never sends anything itself.
* Be polite to the public APIs: one run a day is plenty. The Overpass query covers the whole country and can take a minute.

## Layout

```
horeca_leads/
  sources/bekendmakingen.py  osm.py  news.py  csv_import.py
  enrich.py      website: email/phone, POS & platform fingerprints, chain flag
  scoring.py     weights + reasons
  llm.py         Claude: news extraction + email drafting (structured output)
  templates.py   fallback emails
  pipeline.py    orchestration    store.py  SQLite    report.py  HTML/CSV
tests/           fixtures + end-to-end demo test (pytest)
```
