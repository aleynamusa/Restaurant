# New Restaurant Radar

**Reach restaurants the moment they open.**

An automated system that spots newly listed restaurants on Google Maps, uses AI to fill in the details, and hands sales a lead that is ready to contact.

## The problem

The best moment to sell a POS system is when a restaurant is just opening, before it has chosen one. But finding those restaurants is slow, manual work.

## What it will do

Google does not send an alert when a new place appears, so the radar builds its own.

1. **Take a snapshot.** Every day, scan the restaurants in a region through the official Google Places API and store each place ID.
2. **Detect new places.** Compare with the previous snapshot. A place ID we have not seen before is a newly listed restaurant.
3. **Check what is known.** Does the place have a website or listing with real information?
   - **Info found:** AI (Claude) reads the website and extracts the details: cuisine, table service, online ordering, signs of a new opening. If something is not in the text, it is marked unknown instead of guessed.
   - **No info:** find a public way to reach them (phone on the listing, social page or contact form) so sales can ask for the missing details directly.
4. **Score the fit and draft the message.** A fit score for Winston POS with a one-line reason, the details from Maps kept exactly as listed, and a first message in Dutch or English.
5. **Sales reviews and sends.** The salesperson sees the lead, the reason for the score and the draft. Nothing goes out without a human check.

## Safeguards

- **A person decides.** Every draft is reviewed and sent by a salesperson, never automatically.
- **Business data only.** Business details and public business contact routes, not personal profiles, to stay inside GDPR and email-marketing rules.
- **Every fact has a source,** so sales can check it before reaching out.
- **Official access only.** Detection uses the Places API under Google's terms, and only the place ID is stored long term.

## Run the demo

```bash
pip install -r requirements.txt
python -m horeca_leads run --demo --no-claude     # offline demo with sample data
open output/review.html                           # review the leads
```

The demo uses sample data and other sources (permit notices, OpenStreetMap) to show the scoring, email drafting and review page. The Google Maps snapshot step is the part still to be built.
