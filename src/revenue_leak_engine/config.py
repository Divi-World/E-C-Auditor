"""
Central config. Change NICHE_PRESETS keys or DEFAULT_NICHE to switch niches
without touching pipeline code. See docs/ROADMAP.md for the niche fallback
plan if the current niche stops converting.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# --- Paths -------------------------------------------------------------
# Project root = two levels up from this file (src/revenue_leak_engine/config.py)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
LEADS_DIR = DATA_DIR / "leads"
REPORTS_DIR = DATA_DIR / "reports"
SCREENSHOTS_DIR = DATA_DIR / "screenshots"
LOGS_DIR = DATA_DIR / "logs"
SUPPRESSION_LIST_PATH = DATA_DIR / "suppression_list.csv"

TEMPLATES_DIR = Path(__file__).resolve().parent / "reporting" / "templates"

for d in (LEADS_DIR, REPORTS_DIR, SCREENSHOTS_DIR, LOGS_DIR):
    d.mkdir(parents=True, exist_ok=True)

# --- Meta Ad Library -----------------------------------------------------
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN", "")
META_GRAPH_VERSION = "v19.0"
META_AD_LIBRARY_URL = f"https://graph.facebook.com/{META_GRAPH_VERSION}/ads_archive"

# --- Your sending identity (outreach drafts only, never auto-sent) -------
YOUR_NAME = os.getenv("YOUR_NAME", "")
YOUR_EMAIL = os.getenv("YOUR_EMAIL", "")
YOUR_COMPANY = os.getenv("YOUR_COMPANY", "")

# --- Market sequencing -----------------------------------------------------
# US first: larger budgets, faster payment cycles, simpler compliance than
# most markets. Add countries only once the US pipeline is converting —
# each one roughly multiplies audit + manual-review time.
DEFAULT_COUNTRY = "US"
EXPANSION_COUNTRIES = ["GB", "CA", "AU"]  # add later, in this order

# --- Niche presets -----------------------------------------------------
DEFAULT_NICHE = "beauty"

NICHE_PRESETS = {
    "beauty": [
        "skincare", "vitamin c serum", "clean beauty", "k-beauty",
        "cruelty free skincare", "acne treatment", "anti aging cream",
    ],
    "supplements": [
        "vitamins", "protein powder", "collagen supplement",
        "gummy vitamins", "daily supplement",
    ],
    "pet": [
        "dog treats", "cat food", "pet supplements", "dog chews",
    ],
    "coffee": [
        "coffee subscription", "specialty coffee", "cold brew",
    ],
}

# --- Audit settings -----------------------------------------------------
MOBILE_VIEWPORT = {"width": 390, "height": 844}  # iPhone 12/13-ish
AUDIT_TIMEOUT_MS = 20000

REVIEW_APP_SIGNATURES = ["judge.me", "loox.io", "yotpo", "okendo", "stamped.io"]
EXPRESS_CHECKOUT_SIGNATURES = ["shop-pay", "shopify-pay", "apple-pay", "google-pay"]
