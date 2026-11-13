# New Restaurant Radar (horeca-leads)

**Reach restaurants the moment they open.**

## What the app does

New Restaurant Radar finds restaurants in the Netherlands that recently opened or are about to open, and prepares a lead for sales:

1. **Finds new places** from permit notices (Gemeenteblad), OpenStreetMap, news announcements and CSV imports.
2. **Reads what is known** about each place from its website, using Claude to extract the details (cuisine, table service, online ordering, signs of an opening). Anything it cannot find stays "unknown".
3. **Scores the fit** for Winston POS from 0 to 100, with a one-line reason for every point.
4. **Drafts a first email** in English or Dutch that opens with a real fact about the place.
5. **Shows everything on one page** with a map and list. A salesperson reviews, edits and sends. The app never sends anything itself.

Planned next: detecting new places by comparing daily Google Maps snapshots.

## How to start it

```bash
pip install -r requirements.txt
python -m horeca_leads run --demo --no-claude     # offline demo with sample data
open output/review.html                           # review the leads
```

For live data:

```bash
cp config.example.toml config.toml                # set company, sender name, pitch
export ANTHROPIC_API_KEY=...                      # optional; without it, template emails are used
python -m horeca_leads run
```
