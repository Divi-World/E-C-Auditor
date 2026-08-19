import argparse
import csv
from pathlib import Path
from revenue_leak_engine.config import NICHE_PRESETS, DEFAULT_NICHE, LEADS_DIR, SUPPRESSION_LIST_PATH, DEFAULT_COUNTRY
from revenue_leak_engine.discovery.meta_ads_search import find_advertiser_domains
from revenue_leak_engine.qualification.shopify_detect import is_shopify
from revenue_leak_engine.audit.site_audit import audit_site
from revenue_leak_engine.audit.geo_audit import audit_geo, geo_opportunity_score
from revenue_leak_engine.reporting.report_generator import generate_report, opportunity_score
from revenue_leak_engine.reporting.geo_report_generator import generate_geo_report
from revenue_leak_engine.outreach.outreach_draft import draft_email, draft_geo_email, append_draft_to_log

def load_suppression_list() -> set[str]:
    if not SUPPRESSION_LIST_PATH.exists(): return set()
    with open(SUPPRESSION_LIST_PATH, encoding="utf-8") as f:
        return {row[0].strip().lower() for row in csv.reader(f) if row}

def load_seed_csv(path: str) -> list[dict]:
    """Allows manual injection of domains found via TikTok/Instagram/Articles."""
    candidates = []
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if "domain" in row:
                candidates.append({
                    "domain": row["domain"].strip().lower(),
                    "page_name": row.get("brand", "Manual Seed"),
                    "matched_keyword": "manual",
                    "ad_snapshot_url": ""
                })
    return candidates

def run(niche: str = DEFAULT_NICHE, limit: int = 30, country: str = DEFAULT_COUNTRY, seed_csv: str = None):
    suppressed = load_suppression_list()

    candidates = []
    if seed_csv and Path(seed_csv).exists():
        print(f"[1/4] Loading manual seeds from {seed_csv}...")
        candidates.extend(load_seed_csv(seed_csv))

    if not seed_csv:
        print(f"[1/4] Searching Meta Ad Library for '{niche}' in {country}...")
        keywords = NICHE_PRESETS[niche]
        per_keyword = max(3, limit // len(keywords))
        candidates.extend(find_advertiser_domains(keywords, country=country, per_keyword=per_keyword))

    print(f"  -> {len(candidates)} total candidate domains")

    print("[2/4] Validating domains (Platform-Agnostic Mode)...")
    confirmed = []
    seen = set()
    for c in candidates:
        domain = c["domain"]
        if domain in suppressed or domain in seen: continue
        seen.add(domain)
        
        # OG FIX: We no longer discard non-Shopify stores. 
        # The v7.5 GEO Auditor is platform-agnostic (WooCommerce, BigCommerce, Headless).
        # We still tag Shopify if detected, but we keep ALL e-commerce leads.
        try:
            result = is_shopify(domain)
        except Exception:
            result = {"is_shopify": False, "platform": "unknown"}
            
        confirmed.append({**c, **result})
        
    print(f"  -> {len(confirmed)} valid e-commerce leads (Shopify + Non-Shopify)")

    print("[3/4] Running CRO and GEO audits...")
    scored_leads = []
    healthy_skipped = 0

    for lead in confirmed:
        domain = lead["domain"]
        print(f"  auditing {domain}...")

        # 1. Core site audit (CRO) - Wrapped in try/except to prevent pipeline crashes
        try:
            cro_findings = audit_site(domain)
        except Exception as e:
            print(f"    warning: CRO audit crashed - {e}")
            cro_findings = {"error": str(e), "issues": []}
            
        if cro_findings.get("error"):
            print(f"    warning: CRO audit error - {cro_findings['error']}")

        # 2. Geo audit (Platform Agnostic) - Wrapped in try/except
        try:
            geo_findings = audit_geo(domain)
        except Exception as e:
            print(f"    warning: GEO audit crashed - {e}")
            geo_findings = {"issues": [], "overall_geo_score": 0, "platform_detected": "unknown"}

        # Determine if each audit found issues
        cro_ok = bool(cro_findings.get("issues")) and not cro_findings.get("error")
        geo_ok = bool(geo_findings.get("issues"))

        # Skip if both audits found nothing actionable
        if not cro_ok and not geo_ok:
            print(f"    skipped: healthy on both CRO and GEO")
            healthy_skipped += 1
            continue

        lead_result = {**lead}
        lead_result["platform_detected"] = geo_findings.get("platform_detected", "unknown")

        # Process CRO findings if any
        lead_result["cro_status"] = "complete" if cro_ok else ("error" if cro_findings.get("error") else "healthy")
        if cro_ok:
            cro_score = opportunity_score(cro_findings)
            cro_report = generate_report(cro_findings)
            lead_result.update({
                "cro_score": cro_score,
                "cro_report_path": cro_report
            })
            print(f"    CRO score {cro_score}/10 -> {cro_report}")

            # Generate CRO outreach draft
            cro_draft = draft_email(cro_findings, report_url=cro_report)
            append_draft_to_log(cro_draft)

        # Process GEO findings if any
        if geo_ok:
            geo_score = geo_opportunity_score(geo_findings)
            
            # ENTERPRISE SNIPPET INJECTION: Force JSON-LD into the HTML report
            platform = geo_findings.get("platform_detected", "unknown")
            instructions = {
                "shopify": "For Shopify: Paste this snippet into your <code>theme.liquid</code> file just before the closing <code>&lt;/head&gt;</code> tag, or use a JSON-LD injection app.",
                "woocommerce": "For WooCommerce: Add this to your <code>header.php</code> or use an SEO plugin (like Yoast/RankMath) to inject custom schema.",
                "magento": "For Magento: Inject this via your layout XML (<code>default.xml</code>) or a custom block template.",
                "bigcommerce": "For BigCommerce: Paste this into your <code>HTMLHead.html</code> or use the Script Manager.",
                "unknown": "Implementation: Paste this snippet into the <code>&lt;head&gt;</code> section of your website's global template."
            }
            inst_html = f'<div style="background:rgba(59, 130, 246, 0.1); padding:10px; border-radius:6px; margin:15px 0 5px 0; font-size:13px; color:#93c5fd; border:1px solid rgba(59,130,246,0.3);">💡 <strong>Platform Guide:</strong> {instructions.get(platform, instructions["unknown"])}</div>'
            
            for issue in geo_findings.get("issues", []):
                if "fix_snippet" in issue:
                    safe_snippet = issue["fix_snippet"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    snippet_html = f'{inst_html}<pre style="background:#020617;color:#e2e8f0;padding:15px;border-radius:6px;overflow-x:auto;font-size:13px;line-height:1.5;border:1px solid #334155;"><code>{safe_snippet}</code></pre>'
                    issue["fix"] = issue.get("fix", "") + snippet_html

            geo_report = generate_geo_report(geo_findings)
            lead_result.update({
                "geo_score": geo_score,
                "geo_report_path": geo_report
            })
            print(f"    GEO score {geo_score}/10 -> {geo_report}")

            # Generate GEO outreach draft
            geo_draft = draft_geo_email(geo_findings, report_url=geo_report)
            append_draft_to_log(geo_draft)

        # Combine scores (total will be used for ranking)
        lead_result["total_score"] = lead_result.get("cro_score", 0) + lead_result.get("geo_score", 0)
        scored_leads.append(lead_result)

    # Sort by total score descending
    scored_leads.sort(key=lambda l: l["total_score"], reverse=True)

    # Write ranked CSV with all fields
    ranked_csv = LEADS_DIR / f"{niche}_leads_ranked.csv"
    fieldnames = [
        "opportunity_score", "total_score", "cro_score", "geo_score", "primary_leak", "fix_effort", "cro_status", "domain", "page_name",
        "platform_detected", "matched_keyword", "cro_report_path", "geo_report_path"
    ]
    with open(ranked_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for lead in scored_leads:
            row = {k: lead.get(k, "") for k in fieldnames}
            writer.writerow(row)

    print(f"\n[4/4] Done. {len(scored_leads)} e-commerce leads audited. ({healthy_skipped} skipped as healthy/inconclusive).")
    print(f"  -> Skipped {healthy_skipped} completely healthy sites.")
    print(f"  -> {ranked_csv}")

def cli():
    parser = argparse.ArgumentParser(description="Revenue Leak Engine")
    parser.add_argument("--niche", default=DEFAULT_NICHE, choices=list(NICHE_PRESETS))
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--country", default=DEFAULT_COUNTRY)
    parser.add_argument("--seed-csv", help="Path to a CSV of manually found domains (columns: domain, brand)")
    args = parser.parse_args()
    run(args.niche, args.limit, args.country, args.seed_csv)

if __name__ == "__main__":
    cli()
