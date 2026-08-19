# Revenue Leak Engine: GEO & Agentic Commerce Auditor

An enterprise-grade, platform-agnostic auditing engine that mathematically evaluates a domain's readiness for AI Search (Generative Engine Optimization) and Agentic Commerce. It dynamically scrapes brand assets, evaluates JSON-LD schema integrity, detects enterprise WAF blocks, and generates copy-paste ready JSON-LD fixes alongside B2B outreach drafts.

## 🛠️ Prerequisites & Setup

### 1. Environment Setup
```bash
# Create virtual environment
python -m venv venv

# Activate (Windows / Git Bash / MINGW64)
source venv/Scripts/activate

# Activate (macOS / Linux)
source venv/bin/activate

2. Install Dependencies
bash

1
3. Configuration (Meta Ads API)
If you plan to pull live leads via the Meta Ad Library API, inject your token into the root .env file:
bash

1python -m revenue_leak_engine.pipeline --niche beauty --limit 5 --seed-csv test_seeds.csv

niche can be changed to fashion and co
(If using a Seed CSV, this step is optional).
🚀 Execution Commands
Mode A: Seed CSV (Manual Leads)
Use this mode to audit a specific list of domains you have manually sourced (e.g., from TikTok, Instagram, or industry directories).
1. Create your seed file (seeds.csv):
csv

1234
2. Run the Pipeline:
bash

1
(Note: --niche must match a key in NICHE_PRESETS inside config.py).
Mode B: Meta Ads API (Live Automated Leads)
Use this mode to automatically discover active advertisers currently spending money on Meta platforms and audit them at scale.
Run the Pipeline:
bash

1
📦 Understanding the Outputs
Once the pipeline completes, navigate to the data/ directory to harvest your assets:
data/leads/{niche}_leads_ranked.csv
Your master sales tracker. Contains every audited domain, sorted by their combined CRO/GEO revenue leak score.
data/reports/{domain}_geo.html
The enterprise deliverable. A beautifully formatted, dark-mode HTML report containing the exact, dynamically scraped JSON-LD snippets (with the prospect's real logo, brand name, and live pricing) ready for their developers to copy-paste.
data/logs/outreach_drafts.csv
Your outreach engine. Contains highly personalized, hook-driven B2B email drafts mapped directly to the specific revenue leaks found on each site.
🧠 Architectural Integrity
Platform-Agnostic: Accurately detects and audits Shopify, WooCommerce, Magento, BigCommerce, Salesforce, and Custom Headless builds.
Mathematically Honest: Employs strict WAF/Timeout guards to prevent false-positive scoring. If data cannot be verified, the score is capped or marked as unmeasured.
Zero Hallucinations: Dynamically scrapes live OG tags and meta data to populate fix snippets. Never invents fake prices or SKUs.

1
