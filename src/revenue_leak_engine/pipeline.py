import argparse
import time
import csv
from pathlib import Path
from revenue_leak_engine.config import NICHE_PRESETS, DEFAULT_NICHE, LEADS_DIR, SUPPRESSION_LIST_PATH, DEFAULT_COUNTRY
from revenue_leak_engine.discovery.meta_ads_search import find_advertiser_domains
from revenue_leak_engine.qualification.shopify_detect import is_shopify
from revenue_leak_engine.audit.site_audit import audit_site
from revenue_leak_engine.audit.geo_audit import audit_geo, geo_opportunity_score
from revenue_leak_engine.audit.copy_bank import ISSUE_COPY
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
        meta_leads = find_advertiser_domains(keywords, country=country, per_keyword=per_keyword)
        for ml in meta_leads:
            ml["is_confirmed_advertiser"] = True
        candidates.extend(meta_leads)

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
            from revenue_leak_engine.audit.viewport_profiles import MOBILE_PROFILE, DESKTOP_PROFILE
            cro_findings = audit_site(domain, profile=MOBILE_PROFILE)
        except Exception as e:
            print(f"    warning: CRO audit crashed - {e}")
            cro_findings = {"error": str(e), "issues": []}
            
        if cro_findings.get("error"):
            print(f"    warning: CRO audit error - {cro_findings['error']}")

        time.sleep(2)

        # 2. Geo audit (Platform Agnostic) - Wrapped in try/except
        try:
            geo_findings = audit_geo(domain)
        except Exception as e:
            err_str = str(e).lower()
            if any(x in err_str for x in ["could not resolve", "nameresolutionerror", "gaierror", "dns", "no address associated"]):
                print(f"    warning: GEO audit DNS failure")
                geo_findings = {
                    "issues": [{"code": "dns_resolution_failed", "description": "Domain cannot be resolved (DNS Failure).", "severity": "critical", "confidence": "VERIFIED", "business_impact": "The site is completely inaccessible. Revenue is 100% lost.", "fix": "Check domain registration and DNS provider settings."}],
                    "overall_geo_score": 0, 
                    "platform_detected": "unknown",
                    "audit_status": "INCONCLUSIVE_DNS"
                }
            else:
                print(f"    warning: GEO audit crashed - {e}")
                geo_findings = {"issues": [], "overall_geo_score": 0, "platform_detected": "unknown"}

        # Determine if each audit found issues
        cro_ok = bool(cro_findings.get("issues")) and not cro_findings.get("error")
        geo_ok = bool(geo_findings.get("issues"))

        if geo_findings.get("overall_geo_score", 0) == 0 and not geo_findings.get("issues"):
            geo_findings["audit_status"] = "INCONCLUSIVE_NETWORK"
            geo_findings["issues"].append({
                "code": "network_unreachable",
                "description": "GEO audit could not reach the domain (DNS/Network Failure).",
                "severity": "critical", "confidence": "VERIFIED",
                "business_impact": "The site is completely inaccessible to customers. Revenue is 100% lost.",
                "fix": "Verify domain registration, DNS records, and hosting server status."
            })

        # Skip if both audits found nothing actionable
        if not cro_ok and not geo_ok:
            print(f"    skipped: healthy on both CRO and GEO")
            healthy_skipped += 1
            continue
            
        # Partner Fix: Removed hard-skip for non_commerce_profile. Let it score and route to CSV.

        lead_result = {**lead}
        lead_result["platform_detected"] = geo_findings.get("platform_detected", "unknown")

        # Process CRO findings if any
        lead_result["estimated_monthly_leak_usd"] = cro_findings.get("estimated_monthly_leak_usd", 0)
        lead_result["cro_status"] = "complete" if cro_ok else ("error" if cro_findings.get("error") else "healthy")
        if cro_ok:
            cro_findings["niche"] = niche
            cro_score = opportunity_score(cro_findings)
            cro_report = generate_report(cro_findings)
            try:
                with open(cro_report, 'r', encoding='utf-8') as f: html = f.read()
                if html.count('Enterprise Revenue Leak Engine') > 1:
                    parts = html.split('Enterprise Revenue Leak Engine')
                    html = parts[0] + 'Enterprise Revenue Leak Engine' + ''.join(parts[2:])
                    with open(cro_report, 'w', encoding='utf-8') as f: f.write(html)
            except: pass
            
            # PHASE H: PDF EXPORT
            cro_pdf_path = None
            try:
                from revenue_leak_engine.reporting.pdf_generator import generate_pdf
                cro_pdf_path = generate_pdf(cro_report, cro_report.replace(".html", ".pdf"))
            except Exception: pass

            lead_result.update({
                "cro_score": cro_score,
                "cro_report_path": cro_report,
                "cro_pdf_path": cro_pdf_path or ""
            })

            # Generate High-Tech Outreach Draft
            try:
                from revenue_leak_engine.outreach.email_generator import generate_outreach_email
                email_draft = generate_outreach_email(cro_findings)
                lead_result["outreach_draft"] = email_draft.replace("\n", " | ")
            except Exception as e:
                lead_result["outreach_draft"] = f"Failed: {e}"

            print(f"    CRO score {cro_score}/10 -> {cro_report}")
            
            # Desktop Telemetry (Secondary)
            try:
                desktop_findings = audit_site(domain, profile=DESKTOP_PROFILE)
                desktop_report = generate_report(desktop_findings)
                lead_result["desktop_report_path"] = desktop_report
                print(f"    Desktop telemetry -> {desktop_report}")
            except Exception as e:
                print(f"    warning: Desktop audit crashed - {e}")
                lead_result["desktop_report_path"] = "" 

            # Generate CRO outreach draft
            cro_draft = draft_email(cro_findings, report_url=cro_report)
            append_draft_to_log(cro_draft)

        # Advertiser-Aware Copy Branch (Partner Directive)
        # Meta Ads discovery means they are confirmed advertisers. CSV seeds default to generic.
        is_advertiser = lead.get("is_confirmed_advertiser", False)
        for issue in geo_findings.get("issues", []):
            code = issue.get("code")
            if code in ISSUE_COPY:
                key = "business_impact_advertiser" if is_advertiser else "business_impact_generic"
                issue["business_impact"] = ISSUE_COPY[code].get(key, issue.get("business_impact", ""))

        # Process GEO findings if any
        if geo_ok:
            geo_score = geo_opportunity_score(geo_findings)
            
            # ENTERPRISE SNIPPET INJECTION: Force JSON-LD into the HTML report
            platform = geo_findings.get("platform_detected", "unknown")
            instructions = {
                "shopify": """<strong>🛠️ 10-Point Enterprise SOP (Shopify):</strong><br>
<strong>1. Prerequisites:</strong> Ensure every product has Title, Price, SKU, and Barcode (GTIN) filled in <code>Shopify Admin > Products</code>.<br>
<strong>2. Exact File Path:</strong> <code>Online Store > Themes > Edit Code > sections/main-product.liquid</code> (or <code>theme.liquid</code> before <code>&lt;/head&gt;</code>).<br>
<strong>3. Admin Steps:</strong> Paste the Liquid snippet at the top of the file. Save.<br>
<strong>4. Validation:</strong> Test a live product URL via <a href='https://search.google.com/test/rich-results' target='_blank' style='color:#93c5fd;'>Google Rich Results Test</a>.<br>
<strong>5. Rollback:</strong> Revert via <code>Theme History</code> in the Shopify theme editor if errors occur.<br>
<strong>6. Non-Code (Policies):</strong> Go to <code>Settings > Policies</code> and expand Shipping/Refund templates to >100 words.<br>
<strong>7. Non-Code (Robots.txt):</strong> Create <code>templates/robots.txt.liquid</code> and append AI bot allowances.""",
                "woocommerce": """<strong>🛠️ 10-Point Enterprise SOP (WooCommerce):</strong><br>
<strong>1. Prerequisites:</strong> Populate SKU and GTIN fields in the Product Data meta box.<br>
<strong>2. Exact File Path:</strong> <code>Appearance > Theme File Editor > functions.php</code> (Child Theme recommended).<br>
<strong>3. Admin Steps:</strong> Paste the PHP snippet at the bottom of <code>functions.php</code>. Save.<br>
<strong>4. Validation:</strong> Test via Google Rich Results Test or Schema.org Validator.<br>
<strong>5. Rollback:</strong> Restore <code>functions.php</code> via FTP if a white screen occurs.<br>
<strong>6. Non-Code (Policies):</strong> Create standard Pages for Shipping/Returns and link in <code>Appearance > Menus</code>.<br>
<strong>7. Non-Code (Robots.txt):</strong> Use Yoast SEO > Tools > File Editor to append AI rules.""",
                "bigcommerce": """<strong>🛠️ 10-Point Enterprise SOP (BigCommerce):</strong><br>
<strong>1. Prerequisites:</strong> Populate GTIN/MPN fields in the Product Details tab.<br>
<strong>2. Exact File Path:</strong> <code>Storefront > Script Manager</code> or <code>Edit Theme > templates/components/products/product-view.html</code>.<br>
<strong>3. Admin Steps:</strong> Inject the Handlebars snippet into the script manager or theme file.<br>
<strong>4. Validation:</strong> Verify via Google Rich Results Test.<br>
<strong>5. Rollback:</strong> Delete script from Script Manager or revert theme file.<br>
<strong>6. Non-Code (Policies):</strong> Navigate to <code>Storefront > Web Pages</code> to build policy hubs.<br>
<strong>7. Non-Code (Robots.txt):</strong> Edit server root <code>robots.txt</code> via SSH/FTP.""",
                "magento": """<strong>🛠️ 10-Point Enterprise SOP (Magento):</strong><br>
<strong>1. Prerequisites:</strong> Map Product Attributes for GTIN/Barcode in the Admin Panel.<br>
<strong>2. Exact File Path:</strong> <code>app/design/frontend/[Vendor]/[Theme]/Magento_Catalog/templates/product/view/</code>.<br>
<strong>3. Admin Steps:</strong> Create a custom PHTML block and inject via XML layout (<code>catalog_product_view.xml</code>).<br>
<strong>4. Validation:</strong> Run Rich Results Test and clear cache (<code>bin/magento cache:flush</code>).<br>
<strong>5. Rollback:</strong> Remove XML layout update and flush cache.<br>
<strong>6. Non-Code (Policies):</strong> Use <code>Content > Pages</code> to build policy hubs.<br>
<strong>7. Non-Code (Robots.txt):</strong> Edit <code>pub/robots.txt</code> directly via SSH/FTP.""",
                "unknown": """<strong>🛠️ 10-Point Enterprise SOP (Custom/Headless):</strong><br>
<strong>1. Prerequisites:</strong> Ensure CMS database exposes SKU, Price, and GTIN to frontend.<br>
<strong>2. Exact File Path:</strong> Global <code>&lt;head&gt;</code> layout template (e.g., Next.js <code>_app.js</code>).<br>
<strong>3. Admin Steps:</strong> Inject JSON-LD and map backend variables.<br>
<strong>4. Validation:</strong> Test via Google Rich Results Test.<br>
<strong>5. Rollback:</strong> Revert via Git.<br>
<strong>6. Non-Code (Policies):</strong> Ensure policy routes return >100 words.<br>
<strong>7. Non-Code (Robots.txt):</strong> Update server root <code>robots.txt</code>."""
            }
            inst_html = f'<div style="background:rgba(59, 130, 246, 0.1); padding:10px; border-radius:6px; margin:15px 0 5px 0; font-size:13px; color:#93c5fd; border:1px solid rgba(59,130,246,0.3);">💡 <strong>Platform Guide:</strong> {instructions.get(platform, instructions["unknown"])}</div>'
            
            for issue in geo_findings.get("issues", []):
                # NON-CODE FIX INJECTION (Robots.txt & Policies)
                if issue.get("code") == "ai_crawlers_blocked":
                    issue["fix"] = issue.get("fix", "") + """<br><strong>📋 Exact robots.txt Append Block:</strong><br>
<pre style="background:#020617;color:#e2e8f0;padding:15px;border-radius:6px;overflow-x:auto;font-size:13px;line-height:1.5;border:1px solid #334155;"><code>User-agent: GPTBot
Allow: /
User-agent: ClaudeBot
Allow: /
User-agent: PerplexityBot
Allow: /
User-agent: Applebot-Extended
Allow: /</code></pre>"""
                if issue.get("code") == "missing_answerability_content":
                    issue["fix"] = issue.get("fix", "") + """<br><strong>📋 Admin UI Path:</strong> Navigate to your CMS Pages editor. Create dedicated pages for <code>/policies/shipping</code>, <code>/policies/returns</code>, and <code>/pages/faq</code>. Ensure each contains >100 words of substantive text."""
                
                if "fix_snippet" in issue:
                    safe_snippet = issue["fix_snippet"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    snippet_html = f'{inst_html}<pre style="background:#020617;color:#e2e8f0;padding:15px;border-radius:6px;overflow-x:auto;font-size:13px;line-height:1.5;border:1px solid #334155;"><code>{safe_snippet}</code></pre>'
                    issue["fix"] = issue.get("fix", "") + snippet_html

            
                        
            # DETERMINISTIC OPPORTUNITY TIER (Calculated BEFORE report generation)
            geo_score_val = float(geo_findings.get("overall_geo_score", 0) or 0)
            issue_count = len(geo_findings.get("issues", []))
            if geo_score_val >= 8.0 and issue_count == 0:
                geo_findings["opp_tier"] = "LOW"
                geo_findings["opp_color"] = "#10b981"
            elif geo_score_val >= 8.0 and issue_count > 0:
                geo_findings["opp_tier"] = "MEDIUM"
                geo_findings["opp_color"] = "#f59e0b"
            elif geo_score_val >= 5.0:
                geo_findings["opp_tier"] = "MEDIUM"
                geo_findings["opp_color"] = "#f59e0b"
            else:
                geo_findings["opp_tier"] = "HIGH"
                geo_findings["opp_color"] = "#ef4444"

            geo_report = generate_geo_report(geo_findings)
            try:
                with open(geo_report, 'r', encoding='utf-8') as f: html = f.read()
                if html.count('Enterprise Revenue Leak Engine') > 1:
                    parts = html.split('Enterprise Revenue Leak Engine')
                    html = parts[0] + 'Enterprise Revenue Leak Engine' + ''.join(parts[2:])
                    with open(geo_report, 'w', encoding='utf-8') as f: f.write(html)
            except: pass
            lead_result.update({
                "geo_score": geo_score,
                "geo_report_path": geo_report
            })
            print(f"    GEO score {geo_score}/10 -> {geo_report}")

            # Generate GEO outreach draft
            geo_draft = draft_geo_email(geo_findings, report_url=geo_report)
            append_draft_to_log(geo_draft)

        # Combine scores (total will be used for ranking)
                # Partner Directive: Flag non-commerce profiles instead of dropping or blindly including
        is_non_commerce = any(i.get("code") == "non_commerce_profile" for i in geo_findings.get("issues", []))
        if is_non_commerce:
            lead_result["flagged_non_commerce"] = True
            print(f"    note: non-commerce profile detected, included but flagged for manual review")
        else:
            lead_result["flagged_non_commerce"] = False

        lead_result["total_score"] = lead_result.get("cro_score", 0) + lead_result.get("geo_score", 0)
        
        # Lead Status Classification (Partner Directive #2)
        geo_score_val = geo_findings.get("overall_geo_score", 0) or 0
        geo_issues_count = len(geo_findings.get("issues", []))
        cro_stat = lead_result.get("cro_status", "unknown")
        conf = geo_findings.get("score_confidence", "full")
        
        if geo_issues_count == 0 and geo_score_val >= 8.0:
            lead_result["lead_status"] = "HEALTHY"
        elif cro_stat == "error" and conf in ["partial", "low"]:
            lead_result["lead_status"] = "INCONCLUSIVE"
        else:
            lead_result["lead_status"] = "QUALIFIED_LEAK"
        scored_leads.append(lead_result)

    # Sort by total score descending
    scored_leads.sort(key=lambda l: l["total_score"], reverse=True)

    # Write ranked CSV with all fields
    ranked_csv = LEADS_DIR / f"{niche}_leads_ranked.csv"
    fieldnames = [
        "lead_status", "opportunity_score", "total_score", "cro_score", "geo_score", "primary_leak", "fix_effort", "cro_status", "domain", "page_name",
        "platform_detected", "matched_keyword", "cro_report_path", "geo_report_path"
    , "estimated_monthly_leak_usd", "outreach_draft"]
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
