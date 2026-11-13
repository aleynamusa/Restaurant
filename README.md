# New restaurant radar for Winston POS

## The idea

An automated "new restaurant radar" that finds restaurants in the Netherlands that are about to open or just opened. Those are the places most likely to need a POS. For each one it:

1. **Reads the restaurant's website** and uses Claude to pull out facts: cuisine, table service, online ordering, signs of an upcoming opening.
2. **Scores how well it fits Winston POS** (0–100) and explains why in one line.
3. **Drafts a personal first email** in Dutch or English.
4. **Gives the lead and the draft to a salesperson**, who reviews it and sends it. Nothing is sent automatically.

**Built so far:** this version finds new places through municipal permit notices, OpenStreetMap, news and CSV lists. Daily Google Maps scanning (via the Places API) is the planned next step and hasn't been built yet.

## The demo

The demo runs on bundled sample data, so it needs no internet and no API key:

```bash
python -m horeca_leads run --demo --no-claude
```

It creates `output/review.html`. Open it in a browser and you'll see:

- about 10 sample restaurants on a map, marked **hot / warm / cold**, e.g. *Vesper, Utrecht: 77/100, hot, permit just applied for*
- the reasons behind each score
- a draft email for each lead that you can edit, then **Open in email app**, **Mark sent** or **Skip**

To try it on a single restaurant website:

```bash
python -m horeca_leads prospect --demo --no-claude https://vesper-utrecht.example.nl
```

## Requirements to start

1. **Python 3.10 or newer**
2. **Install the packages:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Run the demo** (see above). That's all you need to see it working.

To use real data instead of the demo:

4. Copy `config.example.toml` to `config.toml` and fill in the sender name, phone number and pitch.
5. *(Optional)* Set an Anthropic API key so Claude writes the emails. Without one, simple template emails are used.
   ```powershell
   $env:ANTHROPIC_API_KEY="your-key"      # Windows PowerShell
   ```
6. Run `python -m horeca_leads run` (or `python -m horeca_leads prospect <website>` for a single restaurant).
