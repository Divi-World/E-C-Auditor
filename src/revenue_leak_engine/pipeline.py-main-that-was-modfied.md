"""
Runs the full lean pipeline end to end:
  1. Meta Ad Library search for the niche keywords (ad-running = budget signal)
  2. Shopify confirmation filter
  3. Mobile CRO audit (Playwright, evidence-based)
  4. Client-ready HTML report per lead, scored by opportunity
  5. Draft outreach email per lead (never auto-sent)

Nothing here sends email or contacts anyone. Every output lands in
data/leads/, data/reports/, data/screenshots/, and data/logs/ for manual
review. See docs/ROADMAP.md for the reasoning behind this sequencing.
"""
import argparse
import csv

from revenue_leak_engine.config import (
    NICHE_PRESETS, DEFAULT_NICHE, LEADS_DIR, SUPPRESSION_LIST_PATH, DEFAULT_COUNTRY,
)
from revenue_leak_engine.discovery.meta_ads_search import find_advertiser_domains
from revenue_leak_engine.qualification.shopify_detect import is_shopify
from revenue_leak_engine.audit.site_audit import audit_site
from revenue_leak_engine.reporting.report_generator import generate_report, opportunity_score
from revenue_leak_engine.outreach.outreach_draft import draft_email, append_draft_to_log


def load_suppression_list() -> set[str]:
    if not SUPPRESSION_LIST_PATH.exists():
        return set()
    with open(SUPPRESSION_LIST_PATH, encoding="utf-8") as f:
        return {row[0].strip().lower() for row in csv.reader(f) if row}


def run(niche: str = DEFAULT_NICHE, limit: int = 30, country: str = DEFAULT_COUNTRY) -> list[dict]:
    """Runs the full pipeline and returns the ranked, audited leads."""
    if niche not in NICHE_PRESETS:
        raise ValueError(f"Unknown niche '{niche}'. Options: {list(NICHE_PRESETS)}")

    suppressed = load_suppression_list()
    keywords = NICHE_PRESETS[niche]
    per_keyword = max(3, limit // len(keywords))

    print(f"[1/4] Searching Meta Ad Library for '{niche}' keywords in {country}...")
    candidates = find_advertiser_domains(keywords, country=country, per_keyword=per_keyword)
    print(f"  -> {len(candidates)} unique advertiser domains found")

    print("[2/4] Confirming Shopify...")
    confirmed = []
    for c in candidates:
        if c["domain"] in suppressed:
            continue
        result = is_shopify(c["domain"])
        if result["is_shopify"]:
            confirmed.append({**c, **result})
    print(f"  -> {len(confirmed)} confirmed Shopify + ad-running leads")

    leads_csv = LEADS_DIR / f"{niche}_leads.csv"
    with open(leads_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "domain", "page_name", "matched_keyword", "confidence", "ad_snapshot_url"
        ])
        writer.writeheader()
        for c in confirmed:
            writer.writerow({k: c.get(k, "") for k in writer.fieldnames})
    print(f"  -> saved {leads_csv}")

    print("[3/4] Running mobile CRO audits + generating reports...")
    scored_leads = []
    for lead in confirmed:
        domain = lead["domain"]
        print(f"  auditing {domain}...")
        findings = audit_site(domain)
        if findings.get("error"):
            print(f"    skipped: {findings['error']}")
            continue

        score = opportunity_score(findings)
        report_path = generate_report(findings)
        print(f"    score {score}/10 -> report {report_path}")

        draft = draft_email(findings, report_url=report_path)
        append_draft_to_log(draft)

        scored_leads.append({**lead, "score": score, "report_path": report_path})

    # Best prospects first — ranking derived from actual evidence found
    # on-site, not a static list.
    scored_leads.sort(key=lambda l: l["score"], reverse=True)

    ranked_csv = LEADS_DIR / f"{niche}_leads_ranked.csv"
    with open(ranked_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "score", "domain", "page_name", "matched_keyword", "report_path"
        ])
        writer.writeheader()
        for lead in scored_leads:
            writer.writerow({k: lead.get(k, "") for k in writer.fieldnames})

    print(f"\n[4/4] Done. {len(scored_leads)} audited leads ranked by opportunity score.")
    print(f"  -> {ranked_csv}  (highest score = strongest pitch, review these first)")
    print("Next step: manually review data/reports/ and data/logs/outreach_drafts.csv "
          "before sending anything.")

    return scored_leads


def cli():
    parser = argparse.ArgumentParser(description="Revenue Leak Engine — lean pipeline")
    parser.add_argument("--niche", default=DEFAULT_NICHE, choices=list(NICHE_PRESETS))
    parser.add_argument("--limit", type=int, default=30, help="approx. candidate domains to pull")
    parser.add_argument("--country", default=DEFAULT_COUNTRY,
                         help="US first — see EXPANSION_COUNTRIES in config.py for what's next")
    args = parser.parse_args()
    run(args.niche, args.limit, args.country)


if __name__ == "__main__":
    cli()
