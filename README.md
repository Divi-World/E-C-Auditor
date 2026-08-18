# Revenue Leak Engine

Finds Shopify beauty/skincare brands currently running Meta ads, audits their
mobile product pages for conversion leaks, generates client-ready reports,
and drafts (never auto-sends) outreach emails. Built to get you real,
qualified leads in days, not after weeks of infrastructure.

For the full plan, sequencing, and reasoning behind every decision, see
**[docs/ROADMAP.md](docs/ROADMAP.md)**.

## Project structure

```
revenue-leak-engine/
├── src/revenue_leak_engine/     # the package
│   ├── discovery/                 # Meta Ad Library search + domain resolution
│   ├── qualification/             # Shopify detection
│   ├── audit/                     # Playwright mobile CRO audit
│   ├── reporting/                 # HTML report generation + scoring
│   ├── outreach/                  # email draft generation
│   ├── pipeline.py                # orchestrates the above, CLI entrypoint
│   └── config.py                  # niches, paths, US-first market sequencing
├── scripts/run_pipeline.py       # run without installing the package
├── tests/                         # pytest unit tests for the pure logic
├── data/                          # generated leads, reports, screenshots, logs
├── docs/ROADMAP.md               # the plan
├── .env.example
├── pyproject.toml
└── requirements.txt
```

## Setup

```bash
# from the project root
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -e ".[dev]"          # installs the package + test deps
playwright install chromium

cp .env.example .env             # then fill in META_ACCESS_TOKEN, YOUR_NAME, etc.
```

## Run

```bash
rle-pipeline --niche beauty --limit 30 --country US
# or, without installing:
python scripts/run_pipeline.py --niche beauty --limit 30 --country US
```

Outputs land in:
- `data/leads/beauty_leads_ranked.csv` — confirmed Shopify + ad-running leads,
  sorted by opportunity score (highest first)
- `data/reports/*.html` — one client-ready audit report per lead
- `data/logs/outreach_drafts.csv` — one draft email per lead, for you to
  review, personalize, and send manually
- `data/screenshots/*.png` — evidence backing each audit finding

**Nothing in this codebase sends email or contacts anyone automatically.**
That review step is intentional — see docs/ROADMAP.md § Compliance.

## Test

```bash
pytest tests/ -v
```

## Switching niche or market

Edit `NICHE_PRESETS` and `DEFAULT_COUNTRY` / `EXPANSION_COUNTRIES` in
`src/revenue_leak_engine/config.py`. The pipeline code doesn't change —
see ROADMAP.md for the reasoning behind the current choices and what to
try next if beauty/US stops converting.
