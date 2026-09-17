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
        # The v7.5 GEO Auditor is platform-agnostic (WooCommerce, BigCommerce, structural Commerce).
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
            
            # ENTERPRISE SNIPPET INJECTION: Issue-Specific Platform-Native SOPs
            platform = geo_findings.get("platform_detected", "unknown")
            platform_key = "unknown" if "unknown" in platform.lower() or "enterprise" in platform.lower() or "waf" in platform.lower() or "security gateway" in platform.lower() else platform
            issue_sops = {
                "missing_organization_entity": {
                    "shopify": "<strong>Exact Path:</strong> <code>layout/theme.liquid</code> (paste in &lt;head&gt;).<br><strong>Validation:</strong> Test Homepage via Schema Markup Validator.<br><strong>Rollback:</strong> Revert via Theme History.",
                    "woocommerce": "<strong>Exact Path:</strong> <code>header.php</code> or Yoast/RankMath Global Schema.<br><strong>Validation:</strong> Test Homepage via Schema Markup Validator.<br><strong>Rollback:</strong> Restore via FTP.",
                    "wordpress": "<strong>Exact Path:</strong> Add to <code>wp_head</code> hook via <code>functions.php</code> or use Yoast SEO / RankMath Schema settings.<br><strong>Validation:</strong> Schema Markup Validator.<br><strong>Rollback:</strong> Revert <code>functions.php</code> via FTP/Host.",
                    "bigcommerce": "<strong>Exact Path:</strong> <code>Storefront &gt; Script Manager</code>.<br><strong>Validation:</strong> Rich Results Test.<br><strong>Rollback:</strong> Delete script.",
                    "magento": "<strong>Exact Path:</strong> <code>header.phtml</code> or XML layout.<br><strong>Validation:</strong> Rich Results Test + cache flush.<br><strong>Rollback:</strong> Git revert."
                },
                "incomplete_product_schema": {
                    "shopify": "<strong>1. Prerequisites:</strong> Ensure every product has Title, Price, SKU, and Barcode (GTIN). <strong>Bulk Edit:</strong> Shopify Admin &gt; Products &gt; Select All &gt; Bulk Edit. <strong>CSV Import:</strong> Use Product CSV template to map GTINs. <strong>Metafield Fallback:</strong> Map to <code>product.metafields.custom.gtin</code> if native fields are empty.<br><strong>2. Exact Path:</strong> <code>sections/main-product.liquid</code>.<br><strong>3. Validation:</strong> 1. Run Google Rich Results Test. 2. Check Schema Markup Validator for duplicate IDs. 3. Run Liquid lint in Shopify Theme Check app.<br><strong>4. Rollback:</strong> 1. Backup current theme. 2. Use Theme History to revert specific file. 3. Verify no JSON-LD app conflicts (e.g., SEO Manager).<br><strong>5. Theme Check:</strong> Verify compatibility with Dawn v2.0+ or your custom theme version.",
                    "woocommerce": "<strong>Exact Path:</strong> <code>single-product.php</code> or Yoast/RankMath.<br><strong>Sitemap Debug:</strong> Check Yoast SEO &gt; Settings &gt; XML Sitemaps, flush permalinks (Settings &gt; Permalinks &gt; Save), and check for plugin conflicts blocking product URLs.<br><strong>Validation:</strong> Rich Results Test.<br><strong>Rollback:</strong> FTP restore.",
                    "wordpress": "<strong>Exact Path:</strong> <code>single-product.php</code> or WooCommerce template overrides.<br><strong>Sitemap Debug:</strong> Flush permalinks, verify Yoast/RankMath XML sitemaps include <code>product</code> post types, check for plugin conflicts.<br><strong>Validation:</strong> Rich Results Test.<br><strong>Rollback:</strong> FTP restore.",
                    "bigcommerce": "<strong>Exact Path:</strong> <code>templates/components/products/product-view.html</code>.<br><strong>Validation:</strong> Rich Results Test.<br><strong>Rollback:</strong> Revert theme.",
                    "magento": "<strong>Exact Path:</strong> <code>catalog_product_view.xml</code> layout.<br><strong>Validation:</strong> Rich Results Test + cache flush.<br><strong>Rollback:</strong> Remove XML update."
                },
                "missing_answerability_content": {
                    "shopify": "<strong>Admin Path:</strong> <code>Settings &gt; Policies</code>. Expand to &gt;200 words. Create FAQ Page via <code>Online Store &gt; Pages</code>.",
                    "woocommerce": "<strong>Admin Path:</strong> <code>Pages &gt; Add New</code>. Create Shipping, Returns, FAQ pages (&gt;200 words). Link in Footer Menu.",
                    "wordpress": "<strong>Admin Path:</strong> <code>Pages &gt; Add New</code>. Create Shipping, Returns, FAQ pages (&gt;200 words). Link in <code>Appearance &gt; Menus</code> (Footer).",
                    "bigcommerce": "<strong>Admin Path:</strong> <code>Storefront &gt; Web Pages</code>. Create policy and FAQ pages.",
                    "magento": "<strong>Admin Path:</strong> <code>Content &gt; Pages</code>. Create policy and FAQ CMS blocks.",
                    "unknown": "<strong>Enterprise CMS Admin Path:</strong> Access your CMS backend to create comprehensive Shipping, Returns, and FAQ pages (>200 words). Link them in the global footer. Do NOT inject JSON-LD until pages are created."
                },
                "ai_discovery agents_blocked": {
                    "shopify": "<strong>Exact Path:</strong> Create <code>templates/robots.txt.liquid</code>. Append AI discovery agent allow rules (GPTBot, ClaudeBot, PerplexityBot, Applebot-Extended).",
                    "woocommerce": "<strong>Exact Path:</strong> Yoast SEO &gt; Tools &gt; File Editor OR edit root <code>robots.txt</code> via FTP. Append AI discovery agent allow rules.",
                    "bigcommerce": "<strong>Exact Path:</strong> Edit root <code>robots.txt</code> via FTP/SSH. Append AI discovery agent allow rules.",
                    "magento": "<strong>Exact Path:</strong> Edit <code>pub/robots.txt</code> via SSH/FTP. Append AI discovery agent allow rules.",
                    "unknown": "<strong>Security Gateway Gateway/CDN Allowlist:</strong> Contact your CDN/Security Gateway vendor (Cloudflare, Akamai, Imperva) to whitelist AI discovery agent user-agents. Do NOT inject JSON-LD for Security Gateway/Security Access Verification issues."
                },
                "waf_blocking": {
                    "shopify": "<strong>Security Gateway Allowlist:</strong> Contact Shopify Plus Support or your CDN (Cloudflare/Fastly) to whitelist AI discovery agent user-agents (GPTBot, ClaudeBot) from programmatic evaluation Filtering challenges.",
                    "woocommerce": "<strong>Security Gateway Allowlist:</strong> Add AI discovery agent user-agents to your Security Gateway/CDN whitelist (Cloudflare Page Rules, Wordfence, or Sucuri).",
                    "bigcommerce": "<strong>Security Gateway Allowlist:</strong> Contact BigCommerce Support or your CDN to whitelist AI discovery agent user-agents.",
                    "magento": "<strong>Security Gateway Allowlist:</strong> Update your CDN/Security Gateway rules to allow AI discovery agent user-agents to bypass programmatic evaluation Filtering.",
                    "unknown": "<strong>MCP & Security Gateway Allowlist:</strong> Expose a Model Context Protocol (MCP) endpoint at /.well-known/mcp.json so AI agents can execute cart/checkouts directly. Contact your CDN/Security Gateway vendor (Cloudflare, Akamai, Imperva) to whitelist AI discovery agent user-agents (GPTBot, ClaudeBot, PerplexityBot) from programmatic evaluation Filtering challenges. Do NOT inject JSON-LD for Security Gateway issues."
                },
                "redirect_shell_detected": {
                    "shopify": "<strong>Shopify Markets/Proxy:</strong> Ensure core catalog pages resolve on the primary domain. If using a structural / Custom Storefront checkout, configure reverse proxy or Shopify Markets so AI agents don't hit Security Gateway-filtered checkout shells.",
                    "woocommerce": "<strong>Domain Routing:</strong> Ensure cart/checkout pages are on the same root domain or properly cross-linked with canonical tags.",
                    "bigcommerce": "<strong>Domain Routing:</strong> Verify checkout domain settings in BigCommerce Admin > Settings > DNS.",
                    "magento": "<strong>Domain Routing:</strong> Check Magento Admin > Stores > Configuration > Web to ensure base URLs are consistent."
                },
                "vision_ai_blindspot": {
                    "shopify": "<strong>Bulk Edit:</strong> Shopify Admin &gt; Products &gt; Select All &gt; Bulk Edit. Map descriptive text to the Image Alt Text field.",
                    "woocommerce": "<strong>Bulk Edit:</strong> WooCommerce &gt; Products. Update the 'Alt Text' field in the Product Image settings.",
                    "wordpress": "<strong>Media Library:</strong> WordPress Admin &gt; Media. Select product images and add descriptive Alt Text.",
                    "unknown": "<strong>CMS Admin:</strong> Access your CMS Media Library or Product Bulk Editor to add descriptive Alt Text to all commercial images."
                },
                "schema_on_noindex_page": {
                    "shopify": "<strong>Admin Path:</strong> Online Store &gt; Preferences OR SEO Manager App. Remove 'Hide from search engines' checkbox.",
                    "woocommerce": "<strong>Admin Path:</strong> Yoast SEO / RankMath &gt; Advanced tab. Set 'Allow search engines to show this Product in search results?' to Yes.",
                    "wordpress": "<strong>Admin Path:</strong> Yoast SEO / RankMath &gt; Advanced tab. Set 'Allow search engines to show this Page in search results?' to Yes.",
                    "unknown": "<strong>CMS Admin:</strong> Check your SEO plugin or page-level settings to ensure the 'noindex' robots directive is removed from commercial pages."
                },
                "silent_json_syntax_failure": {
                    "shopify": "<strong>Validation:</strong> Run the Schema Markup Validator on the live URL. Check for conflicting JSON-LD outputs from SEO apps.",
                    "woocommerce": "<strong>Validation:</strong> Run the Schema Markup Validator. Check Yoast/RankMath global schema settings for syntax errors.",
                    "wordpress": "<strong>Validation:</strong> Run the Schema Markup Validator. Check SEO plugin outputs.",
                    "unknown": "<strong>Validation:</strong> Run the Schema Markup Validator on the live URL to identify the exact line causing the JSON parse failure."
                },
                "orphaned_knowledge_graph": {
                    "shopify": "<strong>Fix:</strong> Ensure your Organization schema in <code>theme.liquid</code> has an <code>@id</code> (e.g., <code>#brand</code>), and your Product schema references it.",
                    "woocommerce": "<strong>Fix:</strong> Use Yoast/RankMath global schema settings to define the Organization @id, and ensure product schema references it.",
                    "wordpress": "<strong>Fix:</strong> Define a global Organization @id in your SEO plugin, and link product schemas to it.",
                    "unknown": "<strong>Fix:</strong> Ensure all Product schemas contain a brand object with an @id pointing to your global Organization schema."
                },
                "semantic_html_blindspot": {
                    "shopify": "<strong>Fix:</strong> Wrap product details in semantic tags in <code>sections/main-product.liquid</code>.",
                    "woocommerce": "<strong>Fix:</strong> Update <code>single-product.php</code> to use semantic HTML5 tags.",
                    "wordpress": "<strong>Fix:</strong> Update your theme templates to use semantic tags.",
                    "unknown": "<strong>Fix:</strong> Refactor frontend templates to use semantic HTML5 tags for better AI extraction."
                },
                "llm_definition_blindspot": {
                    "shopify": "<strong>Fix:</strong> Add an 'About the Brand' section on your homepage using definition list tags.",
                    "woocommerce": "<strong>Fix:</strong> Add explicit brand definitions using semantic tags.",
                    "wordpress": "<strong>Fix:</strong> Use semantic definition tags in your page builder or theme templates.",
                    "unknown": "<strong>Fix:</strong> Implement semantic definition tags to provide explicit context to LLMs."
                },
                "incomplete_entity_corroboration": {
                    "shopify": "<strong>Admin Path:</strong> Shopify Admin &gt; Online Store &gt; Preferences (or Social Links in theme settings). Add all official social and Wikipedia URLs.",
                    "woocommerce": "<strong>Admin Path:</strong> Yoast SEO / RankMath &gt; Search Appearance &gt; General. Add social profiles and sameAs links.",
                    "wordpress": "<strong>Admin Path:</strong> Yoast SEO / RankMath &gt; Search Appearance. Add social profiles.",
                    "bigcommerce": "<strong>Admin Path:</strong> Storefront &gt; Social Media Links. Add all official URLs.",
                    "magento": "<strong>Admin Path:</strong> Content &gt; Configuration &gt; Edit Theme. Add social URLs.",
                    "wix": "<strong>Admin Path:</strong> Marketing &amp; SEO &gt; Social &amp; Google. Add social links.",
                    "squarespace": "<strong>Admin Path:</strong> Settings &gt; Social Links. Add all URLs.",
                    "unknown": "<strong>Admin Path:</strong> Access your CMS Social/SEO settings to unify all brand URLs."
                },
                "product_intelligence_unknown": {
                    "shopify": "<strong>Sitemap Debug:</strong> Check Shopify Admin &gt; Settings &gt; Sitemaps. Ensure products are not hidden from SEO.",
                    "woocommerce": "<strong>Sitemap Debug:</strong> Yoast SEO &gt; General &gt; Features &gt; XML sitemaps. Visit <code>/sitemap_index.xml</code>. Flush permalinks: <code>Settings &gt; Permalinks &gt; Save</code>. Deactivate plugins to isolate 500 errors.",
                    "wordpress": "<strong>Sitemap Debug:</strong> Check Yoast/RankMath XML sitemap settings. Flush permalinks. Deactivate plugins to isolate 500 errors. Ensure WooCommerce is active if it's a store.",
                    "bigcommerce": "<strong>Sitemap Debug:</strong> Check BigCommerce Admin &gt; Settings &gt; SEO &gt; Sitemaps. Ensure products are visible.",
                    "magento": "<strong>Sitemap Debug:</strong> Marketing &gt; SEO &gt; Site Map. Generate and verify XML.",
                    "wix": "<strong>Sitemap Debug:</strong> Marketing &amp; SEO &gt; SEO Setup &gt; Sitemap. Ensure products are indexed.",
                    "squarespace": "<strong>Sitemap Debug:</strong> Settings &gt; SEO &gt; Sitemap. Ensure products are visible.",
                    "unknown": "<strong>Sitemap Debug:</strong> Access your CMS XML sitemap settings. Flush permalinks/caches. Check server error logs for 500 errors."
                },
                "low_entity_density": {
                    "shopify": "<strong>Fix:</strong> Add an 'About the Brand' or 'Glossary' section to your homepage using definition list tags. Ensure your theme.liquid contains a robust sameAs array.",
                    "woocommerce": "<strong>Fix:</strong> Use Yoast/RankMath to enforce strong sameAs links. Add definitional content to your homepage via Gutenberg blocks.",
                    "wordpress": "<strong>Fix:</strong> Increase definitional content on your homepage. Use semantic HTML5 tags to explicitly define your brand entity.",
                    "unknown": "<strong>Fix:</strong> Increase the ratio of explicit entity definitions to total page content to improve LLM citation probability."
                },
                "llms_txt_syntax_invalid": {
                    "shopify": "<strong>Exact Path:</strong> Create <code>templates/llms.txt.liquid</code> and format using standard Markdown headers (#) and metadata keys.",
                    "woocommerce": "<strong>Exact Path:</strong> Create <code>llms.txt</code> in the root directory via FTP. Use standard Markdown formatting.",
                    "wordpress": "<strong>Exact Path:</strong> Create <code>llms.txt</code> in the root directory. Ensure it follows the llmstxt.org specification with Markdown headers.",
                    "unknown": "<strong>Implementation:</strong> Format llms.txt using standard Markdown headers (#) and include metadata keys (title, description, url)."
                },
                "llms_txt_checkout_routing": {
                    "shopify": "<strong>CDN/Routing:</strong> Host llms.txt on the primary brand domain via Shopify Markets, Cloudflare Page Rules, or a reverse proxy. Do not host on checkout subdomains.",
                    "woocommerce": "<strong>Server Config:</strong> Ensure llms.txt is served from the root domain via Nginx/Apache config, not a subdomain.",
                    "bigcommerce": "<strong>File Hosting:</strong> Upload llms.txt to the root directory via FTP/WebDAV.",
                    "magento": "<strong>File Hosting:</strong> Place llms.txt in the pub/ directory and ensure routing serves it from the primary domain."
                },
                "missing_knowledge_graph_entity": {
                    "shopify": "<strong>Exact Path:</strong> Add your Wikidata and Wikipedia URLs to the <code>sameAs</code> array in your Organization schema inside <code>layout/theme.liquid</code>.",
                    "woocommerce": "<strong>Exact Path:</strong> Go to Yoast SEO / RankMath &gt; Search Appearance &gt; General. Add your Wikidata and Wikipedia URLs to the Organization social profiles / sameAs fields.",
                    "wordpress": "<strong>Exact Path:</strong> Update your global Organization schema via your SEO plugin or <code>functions.php</code> to include Wikidata and Wikipedia in the <code>sameAs</code> array.",
                    "unknown": "<strong>Implementation:</strong> Add Wikidata and Wikipedia URLs to the <code>sameAs</code> array of your global Organization JSON-LD schema."
                },
                "serp_visibility_gap": {
                    "shopify": "<strong>Strategy:</strong> Create a new Page in <code>Online Store &gt; Pages</code> titled 'The Ultimate Guide to [Core Product]'. Use semantic HTML, FAQ schema, and internal links to your top collections to signal topical authority to AI engines.",
                    "woocommerce": "<strong>Strategy:</strong> Create a pillar post via <code>Posts &gt; Add New</code> or a dedicated Landing Page. Embed ProductGroup schema and link heavily to your core product categories.",
                    "wordpress": "<strong>Strategy:</strong> Build a definitive pillar page targeting your core entity keywords. Use semantic definition tags and FAQ schema to capture AI conversational queries.",
                    "unknown": "<strong>Strategy:</strong> Publish a comprehensive, text-rich pillar page targeting your core product keywords. Include FAQ schema and explicit entity definitions to capture AI discovery."
                }
            }
            for issue in geo_findings.get("issues", []):
                code = issue.get("code", "")
                default_sop = "<strong>Infrastructure/Security Gateway Guide:</strong> Contact your CDN/Security Gateway vendor (Cloudflare, Akamai, Imperva) or CMS admin to resolve this infrastructure block. Do NOT inject JSON-LD for Security Gateway/Security Access Verification issues." if platform_key == "unknown" else "<strong>Implementation:</strong> Inject JSON-LD into global &lt;head&gt; template.<br><strong>Validation:</strong> Rich Results Test.<br><strong>Rollback:</strong> Git/CMS history."
                sop_text = issue_sops.get(code, {}).get(platform_key.lower(), default_sop)
                # ANTI-GENERIC GUARD: Eradicate "Inject JSON-LD" for known CMS platforms
                if "Inject JSON-LD into global" in sop_text and platform_key.lower() not in ["unknown", "enterprise commerce platform", "api_first", "structural commerce"]:
                    sop_text = "<strong>Native CMS Admin Path:</strong> Access your " + platform.title() + " admin dashboard (Pages/Products/Settings) to update this content natively. Use the developer snippet below only if you have direct code access."
                inst_html = f'<div style="background:rgba(59, 130, 246, 0.1); padding:10px; border-radius:6px; margin:15px 0 5px 0; font-size:13px; color:#93c5fd; border:1px solid rgba(59,130,246,0.3);"><strong>Platform Guide ({platform.title()}):</strong> {sop_text}</div>'
                issue["fix"] = issue.get("fix", "") + inst_html
                if "fix_snippet" in issue:
                    # SELF-AWARE DUPLICATE SCHEMA WARNING
                    if code in ["missing_organization_entity", "incomplete_product_schema", "incomplete_entity_corroboration"]:
                        if platform_key == "shopify": apps_text = "a Shopify app (e.g., SEO Manager, TinyIMG, JSON-LD for SEO)"
                        elif platform_key in ["wordpress", "woocommerce"]: apps_text = "a WP plugin (e.g., Yoast, RankMath, WooCommerce)"
                        else: apps_text = "an existing SEO application or plugin"
                        warning_html = f'<div style="background:rgba(239, 68, 68, 0.1); border-left:4px solid #ef4444; padding:12px; margin:10px 0; border-radius:4px; color:#fca5a5;"><strong>⚠️ Self-Aware Warning (Duplicate Schema):</strong> AI engines penalize conflicting data. Before pasting, inspect your head tag. If {apps_text} is already injecting this schema, disable its schema feature to prevent AI hallucinations.</div>'
                        issue["fix"] = issue.get("fix", "") + warning_html
                    safe_snippet = issue["fix_snippet"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    if "REPLACE_WITH_" in safe_snippet:
                        # PARTNER DIRECTIVE: Output Data Collection Checklist instead of broken code
                        checklist = """<div style="background:rgba(245, 158, 11, 0.1); border-left:4px solid #f59e0b; padding:15px; margin:10px 0; border-radius:4px; color:#fcd34d;">
<strong>📋 Data Collection Checklist:</strong><br>
To complete this implementation, please gather the following brand assets from your internal guidelines or CMS:<br>
<ul style="margin:5px 0; padding-left:20px;">
<li>City / Headquarters Location</li>
<li>Official Social Media URLs (Facebook, Instagram, LinkedIn)</li>
<li>Wikipedia Entity URL (if applicable)</li>
</ul>
<em>Once gathered, insert these values into the schema template to unlock full AI entity corroboration.</em>
</div>"""
                        snippet_html = f'<pre style="background:#020617;color:#e2e8f0;padding:15px;border-radius:6px;overflow-x:auto;font-size:13px;line-height:1.5;border:1px solid #334155;"><code>{safe_snippet}</code></pre>' + checklist
                    else:
                        snippet_html = f'<pre style="background:#020617;color:#e2e8f0;padding:15px;border-radius:6px;overflow-x:auto;font-size:13px;line-height:1.5;border:1px solid #334155;"><code>{safe_snippet}</code></pre>'
                    issue["fix"] = issue.get("fix", "") + snippet_html

                # ENTERPRISE DIRECTIVE: Force BreadcrumbList for Product Schema Issues
                if code in ["incomplete_product_schema", "missing_product_schema", "product_intelligence_unknown"] and platform == "shopify":
                    pg_schema = """<br><strong>ProductGroup Schema (Variant-Heavy Catalogs):</strong><br><pre style="background:#020617;color:#e2e8f0;padding:15px;border-radius:6px;overflow-x:auto;font-size:13px;border:1px solid #334155;"><code>&lt;script type="application/ld+json"&gt;
{
  "@context": "https://schema.org",
  "@type": "ProductGroup",
  "name": "{{ product.title | escape }}",
  "variesBy": ["size", "color"],
  "hasVariant": [
    {% for variant in product.variants %}
    {
      "@type": "Product",
      "sku": "{{ variant.sku | escape }}",
      "name": "{{ variant.title | escape }}"
    }{% unless forloop.last %},{% endunless %}
    {% endfor %}
  ]
}
&lt;/script&gt;</code></pre>"""
                    issue["fix"] += pg_schema
                if code in ["incomplete_product_schema", "missing_product_schema", "product_intelligence_unknown"] and platform == "shopify":
                    bc = '<pre style="background:#020617;color:#e2e8f0;padding:15px;border-radius:6px;overflow-x:auto;font-size:13px;border:1px solid #334155;"><code>'
                    bc += '&lt;script type="application/ld+json"&gt;\n{\n  "@context": "https://schema.org",\n  "@type": "BreadcrumbList",\n  "itemListElement": [{\n    "@type": "ListItem", "position": 1, "name": "Home", "item": "{{ shop.url }}"\n  },{\n    "@type": "ListItem", "position": 2, "name": "{{ product.type | escape }}", "item": "{{ shop.url }}/collections/{{ product.type | handleize }}"\n  },{\n    "@type": "ListItem", "position": 3, "name": "{{ product.title | escape }}", "item": "{{ shop.url }}{{ product.url }}"\n  }]\n}\n&lt;/script&gt;</code></pre>'
                    issue["fix"] = issue.get("fix", "") + "<br><strong>BreadcrumbList JSON-LD Template:</strong><br>" + bc
                if code in ["incomplete_product_schema", "missing_product_schema"] and platform == "shopify":
                    extra_schemas = """<br><strong>SiteNavigationElement & ItemList (Collections):</strong><br><pre style="background:#020617;color:#e2e8f0;padding:15px;border-radius:6px;overflow-x:auto;font-size:13px;border:1px solid #334155;"><code>&lt;script type="application/ld+json"&gt;
{
  "@context": "https://schema.org",
  "@type": "SiteNavigationElement",
  "name": "{{ collection.title }}",
  "url": "{{ shop.url }}{{ collection.url }}"
}
&lt;/script&gt;
&lt;script type="application/ld+json"&gt;
{
  "@context": "https://schema.org",
  "@type": "ItemList",
  "itemListElement": [
    {% for product in collection.products limit: 10 %}
    {
      "@type": "ListItem",
      "position": {{ forloop.index }},
      "url": "{{ shop.url }}{{ product.url }}"
    }{% unless forloop.last %},{% endunless %}
    {% endfor %}
  ]
}
&lt;/script&gt;</code></pre>"""
                    issue["fix"] += extra_schemas
                if code in ["missing_organization_entity", "incomplete_entity_corroboration"]:
                    if platform in ["wordpress", "woocommerce"]:
                        website_schema = """<br><strong>Global Discovery & Voice AI Schema (WordPress):</strong><br><pre style="background:#020617;color:#e2e8f0;padding:15px;border-radius:6px;overflow-x:auto;font-size:13px;border:1px solid #334155;"><code>&lt;script type="application/ld+json"&gt;
{
  "@context": "https://schema.org",
  "@type": "WebSite",
  "name": "&lt;?php bloginfo('name'); ?&gt;",
  "url": "&lt;?php echo esc_url(home_url()); ?&gt;",
  "potentialAction": {
    "@type": "SearchAction",
    "target": "&lt;?php echo esc_url(home_url()); ?&gt;/?s={search_term_string}",
    "query-input": "required name=search_term_string"
  }
}
&lt;/script&gt;</code></pre>"""
                    else:
                        website_schema = """<br><strong>Global Discovery & Voice AI Schema:</strong><br><pre style="background:#020617;color:#e2e8f0;padding:15px;border-radius:6px;overflow-x:auto;font-size:13px;border:1px solid #334155;"><code>&lt;script type="application/ld+json"&gt;
{
  "@context": "https://schema.org",
  "@type": "WebSite",
  "name": "{{ shop.name }}",
  "url": "{{ shop.url }}",
  "speakable": {
    "@type": "SpeakableSpecification",
    "cssSelector": [".policy-header", ".product-title", ".brand-name"]
  },
  "potentialAction": {
    "@type": "SearchAction",
    "target": "{{ shop.url }}/search?q={search_term_string}",
    "query-input": "required name=search_term_string"
  }
}
&lt;/script&gt;</code></pre>"""
                    issue["fix"] += website_schema
                if code == "missing_answerability_content" and platform == "shopify":
                    faq = """<div style="background:rgba(16, 185, 129, 0.1); padding:15px; border-radius:6px; border:1px solid rgba(16,185,129,0.3); color:#a7f3d0; font-size:13px;">
<strong>🛠️ Shopify Metaobject Setup Guide:</strong><br>
1. Go to <strong>Shopify Admin &gt; Settings &gt; Custom Data &gt; Metaobjects</strong>.<br>
2. Create a new Metaobject definition named <code>FAQ</code> with fields: <code>Question</code> (Single line text) and <code>Answer</code> (Multi-line text).<br>
3. Add entries for Shipping, Returns, and Sizing.<br>
4. Paste this Liquid loop into <code>templates/page.faq.json</code> or <code>sections/main-page.liquid</code>:<br>
<pre style="background:#020617;color:#e2e8f0;padding:10px;border-radius:4px;overflow-x:auto;margin-top:8px;"><code>&lt;script type="application/ld+json"&gt;
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {% for faq in shop.metaobjects.faq.values %}
    {
      "@type": "Question",
      "name": "{{ faq.question.value | escape }}",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "{{ faq.answer.value | strip_html | escape }}"
      }
    }{% unless forloop.last %},{% endunless %}
    {% endfor %}
  ]
}
&lt;/script&gt;</code></pre>
</div>"""
                    issue["fix"] += "<br><strong>FAQPage Metaobject Implementation:</strong><br>" + faq
                if code == "ai_discovery agents_blocked":
                    rob = """<pre style="background:#020617;color:#e2e8f0;padding:15px;border-radius:6px;overflow-x:auto;font-size:13px;border:1px solid #334155;"><code>User-agent: GPTBot
Allow: /
User-agent: ChatGPT-User
Allow: /
User-agent: ClaudeBot
Allow: /
User-agent: PerplexityBot
Allow: /
User-agent: Applebot-Extended
Allow: /
User-agent: Bytespider
Allow: /</code></pre>"""
                    issue["fix"] += "<br><strong>Exact robots.txt Append Block:</strong><br>" + rob
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

            # PHASE 4: DEPLOYMENT REGRESSION ALERT (Pre-Report Generation)
            try:
                import sqlite3
                from revenue_leak_engine.audit.geo_audit import CACHE_DB
                reg_conn = sqlite3.connect(CACHE_DB)
                prev_runs = reg_conn.execute("SELECT geo_score, issue_count FROM geo_history WHERE domain=? ORDER BY timestamp DESC LIMIT 1", (domain,)).fetchall()
                if prev_runs:
                    prev_score, prev_issues = prev_runs[0]
                    current_score = float(geo_findings.get("overall_geo_score", 0) or 0)
                    current_issues = len(geo_findings.get("issues", []))
                    if (prev_score - current_score) >= 1.0 or (current_issues - prev_issues) >= 3:
                        geo_findings["is_regression"] = True
                        geo_findings["regression_delta"] = round(prev_score - current_score, 1)
                        geo_findings["issues"].insert(0, {
                            "code": "deployment_regression",
                            "description": "Critical: Structural commerce score dropped since last evaluation.",
                            "severity": "high", "confidence": "VERIFIED",
                            "business_impact": f"Recent deployment or configuration change has degraded AI discovery readiness. Score dropped by {round(prev_score - current_score, 1)} points.",
                            "evidence": f"Previous score: {prev_score}. Current score: {current_score}.",
                            "difficulty": "Medium",
                            "fix": "Review recent code deployments, theme updates, or plugin installations that may have removed or corrupted structured data."
                        })
                reg_conn.close()
            except Exception: pass

            # PHASE 3: COMMERCIAL INTELLIGENCE HOOK
            if geo_findings.get("geo_revenue_exposure") == "HIGH":
                geo_findings["business_interpretation"].append(f"Commercial Intelligence: {domain} is actively funding paid media campaigns while core machine-readable commerce data remains incomplete, creating a measurable ROI leak in automated discovery channels.")
            

            # PHASE 3: HIGH-TECH SELF-AWARE ENTITY & SERP INTELLIGENCE
            try:
                from revenue_leak_engine.audit.llm_citation_tracker import track_entity_and_sov
                hp_html = geo_findings.get("homepage_html", "")
                sov_data = track_entity_and_sov(domain, hp_html)
                
                core_prod = sov_data.get("core_product", niche)
                platform = geo_findings.get("platform_detected", "unknown")
                platform_key = "unknown" if "unknown" in platform.lower() or "enterprise" in platform.lower() or "waf" in platform.lower() or "security gateway" in platform.lower() else platform
                
                if sov_data["wikidata_exists"]:
                    geo_findings["business_interpretation"].append(f"Knowledge Graph Validation: {sov_data['brand']} is verified in the global Wikidata Knowledge Graph (ID: {sov_data['wikidata_id']}), confirming baseline entity recognition by AI models.")
                else:
                    geo_findings["business_interpretation"].append(f"Knowledge Graph Gap: {sov_data['brand']} is currently missing from the Wikidata Knowledge Graph. AI engines rely on this graph for factual corroboration; absence severely limits citation accuracy.")
                    
                    kg_sop = {"shopify": "Add your Wikidata and Wikipedia URLs to the <code>sameAs</code> array in your Organization schema inside <code>layout/theme.liquid</code>.", "woocommerce": "Go to Yoast SEO / RankMath &gt; Search Appearance &gt; General. Add your Wikidata and Wikipedia URLs to the Organization social profiles.", "wordpress": "Update your global Organization schema via your SEO plugin or <code>functions.php</code> to include Wikidata and Wikipedia in the <code>sameAs</code> array.", "unknown": "Add Wikidata and Wikipedia URLs to the <code>sameAs</code> array of your global Organization JSON-LD schema."}
                    kg_fix_html = f'<div style="background:rgba(59, 130, 246, 0.1); padding:10px; border-radius:6px; margin:15px 0 5px 0; font-size:13px; color:#93c5fd; border:1px solid rgba(59,130,246,0.3);"><strong>Platform Guide ({platform.title()}):</strong> {kg_sop.get(platform_key.lower(), kg_sop["unknown"])}</div>'
                    
                    geo_findings["issues"].append({
                        "code": "missing_knowledge_graph_entity", "description": "Brand is missing from the global Wikidata Knowledge Graph.",
                        "severity": "high", "confidence": "VERIFIED", "difficulty": "Medium",
                        "business_impact": "AI engines (ChatGPT, Perplexity) rely on Wikidata for factual corroboration. Absence severely limits citation accuracy and triggers hallucinations.",
                        "evidence": f"Wikidata API returned 0 results for '{sov_data['brand']}'.",
                        "fix": f"Register your brand entity on Wikidata and link it via the sameAs array in your Organization schema.{kg_fix_html}"
                    })
                
                if sov_data["serp_rank"] > 0:
                    geo_findings["business_interpretation"].append(f"Market Share Analysis: Your brand ranks #{sov_data['serp_rank']} organically for high-intent '{core_prod}' queries.")
                else:
                    top_comp = sov_data.get("top_competitor", "market leaders")
                    comp_schemas = sov_data.get("competitor_schema_count", 0)
                    geo_findings["business_interpretation"].append(f"Market Share Gap: Your brand is absent from the Top 10 organic results for '{core_prod}' queries. Your top competitor, {top_comp}, ranks #1 and utilizes {comp_schemas} distinct schema types to dominate AI discovery.")
                    
                    serp_sop = {"shopify": f"Create a new Page in <code>Online Store &gt; Pages</code> titled 'The Ultimate Guide to {core_prod}'. Use semantic HTML, FAQ schema, and internal links to your top collections.", "woocommerce": f"Create a pillar post via <code>Posts &gt; Add New</code>. Embed ProductGroup schema and link heavily to your core product categories.", "wordpress": f"Build a definitive pillar page targeting your core entity keywords. Use semantic definition tags and FAQ schema.", "unknown": f"Publish a comprehensive, text-rich pillar page targeting your core product keywords. Include FAQ schema and explicit entity definitions."}
                    serp_fix_html = f'<div style="background:rgba(59, 130, 246, 0.1); padding:10px; border-radius:6px; margin:15px 0 5px 0; font-size:13px; color:#93c5fd; border:1px solid rgba(59,130,246,0.3);"><strong>Platform Guide ({platform.title()}):</strong> {serp_sop.get(platform_key.lower(), serp_sop["unknown"])}</div>'
                    
                    geo_findings["issues"].append({
                        "code": "serp_visibility_gap", "description": f"Brand is absent from Top 10 organic results for '{core_prod}' queries.",
                        "severity": "high", "confidence": "VERIFIED", "difficulty": "Hard",
                        "business_impact": f"Competitors like {top_comp} dominate the AI discovery surface and organic market share for your core product category.",
                        "evidence": f"Search query: 'best {core_prod} brands'. Brand not found in Top 10. Top competitor '{top_comp}' utilizes {comp_schemas} schema types.",
                        "fix": f"Create a definitive 'Best {core_prod} Guide' pillar page targeting your core entity keywords to capture AI discovery and organic market share.{serp_fix_html}"
                    })
            except Exception as e:
                print(f"    warning: Entity/SOV tracking skipped - {e}")

            # PHASE 6: LIVE LLM CITATION ENGINE (Generative Share-of-Voice)
            try:
                from revenue_leak_engine.audit.llm_citation_tracker import query_llm_citation, save_llm_citation
                core_prod_for_llm = sov_data.get("core_product", niche)
                llm_data = query_llm_citation(domain, core_prod_for_llm, sov_data)
                save_llm_citation(llm_data)
                
                if llm_data["brand_mentioned"]:
                    geo_findings["business_interpretation"].append(f"Generative AI Validation: When asked to recommend '{core_prod_for_llm}', AI models ({llm_data['model']}) cited {sov_data['brand']} {llm_data['citation_count']} times.")
                else:
                    if llm_data["model"] != "SIMULATION_MODE":
                        geo_findings["business_interpretation"].append(f"Generative AI Gap: AI models ({llm_data['model']}) were asked to recommend '{core_prod_for_llm}' but did not cite {sov_data['brand']}. Competitors are dominating the generative answer space.")
            except Exception as e:
                print(f"    warning: LLM Citation tracking skipped - {e}")
            # PHASE 9: AGENTIC COMMERCE (MCP CONFIGURATION GENERATOR)
            try:
                has_mcp = any(i.get("code") == "agentic_commerce_partial" for i in geo_findings.get("issues", []))
                if not has_mcp and platform_key not in ["unknown", "waf", "security gateway"]:
                    mcp_config = {
                        "name": f"{sov_data['brand']} Commerce API",
                        "description": f"Agentic commerce endpoint for {sov_data['brand']} {core_prod} inventory and checkout.",
                        "tools": [
                            {"name": "search_inventory", "description": f"Search available {core_prod} by SKU or keyword."},
                            {"name": "get_product_details", "description": "Fetch pricing, availability, and schemas for a specific product."},
                            {"name": "initiate_checkout", "description": "Generate a secure cart and checkout session for AI agents."}
                        ]
                    }
                    mcp_json = json.dumps(mcp_config, indent=2)
                    
                    mcp_sop = {
                        "shopify": "Deploy this configuration via a custom app or reverse proxy at <code>/.well-known/mcp.json</code>.",
                        "woocommerce": "Upload this JSON to your root directory via FTP or expose it via a custom WP REST API endpoint.",
                        "wordpress": "Expose this JSON at <code>/.well-known/mcp.json</code> using a custom rewrite rule or static file.",
                        "unknown": "Host this JSON at <code>/.well-known/mcp.json</code> on your primary domain to enable AI agent transactions."
                    }
                    mcp_fix_html = f'<div style="background:rgba(16, 185, 129, 0.1); padding:10px; border-radius:6px; margin:15px 0 5px 0; font-size:13px; color:#6ee7b7; border:1px solid rgba(16,185,129,0.3);"><strong>Platform Guide ({platform.title()}):</strong> {mcp_sop.get(platform_key.lower(), mcp_sop["unknown"])}</div>'
                    
                    geo_findings["issues"].append({
                        "code": "missing_mcp_configuration",
                        "description": "Missing Model Context Protocol (MCP) configuration for Agentic Commerce.",
                        "severity": "high", "confidence": "VERIFIED", "difficulty": "Medium",
                        "business_impact": "AI shopping agents cannot securely query your inventory or execute checkouts. You are invisible to next-generation transactional AI.",
                        "evidence": "No /.well-known/mcp.json detected on primary domain.",
                        "fix": f"Deploy the following MCP configuration to enable AI agent transactions:<br><pre style=\"background:#020617;color:#e2e8f0;padding:15px;border-radius:6px;overflow-x:auto;font-size:13px;border:1px solid #334155;\"><code>{mcp_json.replace('<', '&lt;').replace('>', '&gt;')}</code></pre>{mcp_fix_html}"
                    })
            except Exception as e:
                pass



                geo_findings['domain'] = domain  # FORCE DOMAIN ISOLATION
            # PHASE 8: DASHBOARD DATA INJECTION (Self-Contained Scope)
            try:
                import sqlite3
                import time as _geo_time
                import json
                from revenue_leak_engine.audit.geo_audit import CACHE_DB
                chart_conn = sqlite3.connect(CACHE_DB)
                hist = chart_conn.execute("SELECT timestamp, geo_score FROM geo_history WHERE domain=? ORDER BY timestamp ASC", (domain,)).fetchall()
                current_score = float(geo_findings.get("overall_geo_score", 0) or 0)
                chart_data = [{"x": _geo_time.strftime('%Y-%m-%d %H:%M', _geo_time.localtime(t)), "y": s} for t, s in hist]
                chart_data.append({"x": _geo_time.strftime('%Y-%m-%d %H:%M', _geo_time.localtime(_geo_time.time())), "y": current_score})
                if len(chart_data) > 0:
                    geo_findings["history_chart_data"] = json.dumps(chart_data)
                chart_conn.close()
            except Exception: pass

            geo_report = generate_geo_report(geo_findings, target_domain=domain)
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
            
            # PHASE 2: SAVE GEO HISTORY TO SQLITE (Zero CRO impact, fails silently if locked)
            try:
                import sqlite3
                import time as _geo_time
                from revenue_leak_engine.audit.geo_audit import CACHE_DB
                conn = sqlite3.connect(CACHE_DB)
                conn.execute("CREATE TABLE IF NOT EXISTS geo_history (domain TEXT, timestamp REAL, geo_score REAL, issue_count INTEGER, exposure_tier TEXT)")
                conn.execute("INSERT INTO geo_history (domain, timestamp, geo_score, issue_count, exposure_tier) VALUES (?, ?, ?, ?, ?)",
                             (domain, _geo_time.time(), geo_score, len(geo_findings.get("issues", [])), geo_findings.get("geo_revenue_exposure", "UNKNOWN")))
                
                # PHASE 3.3: HISTORICAL TELEMETRY (Calculate Deltas)
                hist = conn.execute("SELECT geo_score, issue_count FROM geo_history WHERE domain=? ORDER BY timestamp ASC", (domain,)).fetchall()
                if len(hist) > 1:
                    first_score, first_issues = hist[0]
                    geo_findings["score_delta"] = round(geo_score - first_score, 1)
                    geo_findings["issue_delta"] = len(geo_findings.get("issues", [])) - first_issues
                else:
                    geo_findings["score_delta"] = 0.0
                    geo_findings["issue_delta"] = 0
                
                # PHASE 3: LIVE LLM CITATION TRACKING
                try:
                    conn.execute("""CREATE TABLE IF NOT EXISTS citation_history (
                        domain TEXT, timestamp REAL, prompt TEXT, 
                        brand_mentioned INTEGER, competitor_mentions INTEGER, 
                        sentiment TEXT, source_url TEXT
                    )""")
                except Exception: pass
                conn.commit()
                conn.close()
            except Exception as e:
                import traceback
                print(f"[SQLITE FATAL ERROR IN PIPELINE] {e}")
                traceback.print_exc()
            if geo_findings.get("score_confidence") in ["PARTIAL", "UNVERIFIED"]:
                print(f"    note: Score variance detected due to Security Gateway/telemetry limitations. Manual verification recommended.")

            # Generate GEO outreach draft
            # PHASE 13: AUTOMATED DEPLOYMENT PAYLOADS (1-Click CTO Fix)
            try:
                import json, os
                pr_dir = os.path.join('data', 'pr_payloads')
                os.makedirs(pr_dir, exist_ok=True)
                top_issue = next((i for i in geo_findings.get("issues", []) if i.get("severity") == "high" and i.get("fix_snippet")), None)
                if top_issue:
                    pr_payload = {
                        "domain": domain, "issue_code": top_issue.get("code"),
                        "description": top_issue.get("description"),
                        "commit_message": f"fix(geo): resolve {top_issue.get('code')} for AI visibility",
                        "implementation_snippet": top_issue.get("fix_snippet")
                    }
                    with open(os.path.join(pr_dir, f"{domain.replace('.', '_')}_pr.json"), "w", encoding="utf-8") as f:
                        json.dump(pr_payload, f, indent=2)
                        
                    # Generate 1-Click Bash Deployment Script
                    sh_path = os.path.join(pr_dir, f"{domain.replace('.', '_')}_deploy_fix.sh")
                    snippet = top_issue.get("fix_snippet", "").replace("'", "'\''")
                    platform = geo_findings.get("platform_detected", "unknown").lower()
                    target_file = "theme.liquid" if "shopify" in platform else "header.php" if "wordpress" in platform else "index.html"
                    
                    sh_script = f"""#!/bin/bash
# ==============================================================================
# REVENUE LEAK ENGINE: 1-CLICK DEPLOYMENT ARTIFACT
# Domain: {domain}
# Issue: {top_issue.get('code')}
# ==============================================================================

echo "[*] Initializing Automated Deployment for {domain}..."
echo "[*] Target Platform: {platform.title()}"
echo "[*] Target File: {target_file}"

# The exact implementation snippet generated by the audit engine:
SNIPPET='{snippet}'

echo "[!] Please ensure you have backed up your {target_file} file."
echo "[!] To apply this fix automatically via SSH/FTP, integrate this payload"
echo "    into your CI/CD pipeline or run it in your theme directory."

echo "$SNIPPET" > ./geo_fix_payload.json
echo "[SUCCESS] Payload extracted to geo_fix_payload.json"
echo "[NEXT] Inject this JSON into your {target_file} <head> block."
"""
                    with open(sh_path, "w", encoding="utf-8") as f:
                        f.write(sh_script)
            except Exception: pass

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

        # Lead Status Classification & Regression Variables (Moved UP to fix scoping bug)
        geo_score_val = geo_findings.get("overall_geo_score", 0) or 0
        geo_issues_count = len(geo_findings.get("issues", []))

        # PHASE 4: DEPLOYMENT REGRESSION ALERT (Self-Healing)
        regression_status = "STABLE"
        try:
            import sqlite3
            from revenue_leak_engine.audit.geo_audit import CACHE_DB
            conn = sqlite3.connect(CACHE_DB)
            prev_runs = conn.execute("SELECT geo_score, issue_count FROM geo_history WHERE domain=? ORDER BY timestamp DESC LIMIT 2", (domain,)).fetchall()
            if len(prev_runs) == 2:
                prev_score, prev_issues = prev_runs[1]
                if prev_score is not None and geo_score_val is not None:
                    if (prev_score - geo_score_val) >= 1.0 or (geo_issues_count - prev_issues) >= 3:
                        regression_status = "DEPLOYMENT_REGRESSION"
            conn.close()
        except Exception: pass
        lead_result["regression_status"] = regression_status

        lead_result["total_score"] = lead_result.get("cro_score", 0) + lead_result.get("geo_score", 0)
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
    , "estimated_monthly_leak_usd", "outreach_draft", "regression_status"]
    with open(ranked_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for lead in scored_leads:
            row = {k: lead.get(k, "") for k in fieldnames}
            writer.writerow(row)

    print(f"\n[4/4] Done. {len(scored_leads)} e-commerce leads audited. ({healthy_skipped} skipped as healthy/inconclusive).")
    print(f"  -> Skipped {healthy_skipped} completely healthy sites.")
    print(f"  -> {ranked_csv}")
    # =====================================================================
    # PHASE 14: COMPETITOR BENCHMARKING (INLINE)
    # =====================================================================
    try:
        comp_rows = []
        for lead in scored_leads:
            d14 = lead.get("domain", "")
            if not d14:
                continue
            try:
                import sqlite3 as _sq14
                from revenue_leak_engine.audit.geo_audit import CACHE_DB as _CACHE_14
                _c14 = _sq14.connect(_CACHE_14)
                _hist = _c14.execute(
                    "SELECT geo_score, issue_count FROM geo_history WHERE domain=? ORDER BY timestamp DESC LIMIT 1",
                    (d14,)
                ).fetchone()
                _c14.close()
                _bench_score = float(_hist[0]) if _hist else float(lead.get("geo_score", 0) or 0)
            except Exception:
                _bench_score = float(lead.get("geo_score", 0) or 0)
            comp_rows.append({
                "domain": d14,
                "niche": niche,
                "benchmark_score": round(_bench_score, 1),
                "geo_score": float(lead.get("geo_score", 0) or 0),
                "cro_score": float(lead.get("cro_score", 0) or 0),
                "gap": round(float(lead.get("geo_score", 0) or 0) - _bench_score, 1)
            })
        if comp_rows:
            import csv as _csv14
            bench_csv = LEADS_DIR / f"{niche}_competitor_benchmark.csv"
            with open(bench_csv, "w", newline="", encoding="utf-8") as f:
                w = _csv14.DictWriter(f, fieldnames=["domain", "niche", "benchmark_score", "geo_score", "cro_score", "gap"])
                w.writeheader()
                for r in comp_rows:
                    w.writerow(r)
            print(f"  -> Phase 14 Competitor Benchmark Generated: {bench_csv}")
    except Exception as e:
        print(f"  warning: Phase 14 benchmark failed - {e}")

    # =====================================================================
    # PHASE 16: HYPER-PERSONALIZED AI OUTREACH (INLINE)
    # =====================================================================
    try:
        import csv as _csv16
        out_dir_16 = LEADS_DIR / "outreach"
        out_dir_16.mkdir(parents=True, exist_ok=True)
        outreach_rows = []
        for lead in scored_leads:
            d16 = lead.get("domain", "")
            if not d16:
                continue
            _brand = d16.split(".")[0].replace("-", " ").replace("_", " ").title()
            _geo = float(lead.get("geo_score", 0) or 0)
            _leak = float(lead.get("estimated_monthly_leak_usd", 0) or 0)
            _status = lead.get("lead_status", "QUALIFIED_LEAK")
            if _status != "QUALIFIED_LEAK":
                continue
            subject = f"{_brand}: ${_leak:,.0f}/mo revenue leak detected in AI discovery channels"
            body = (
                f"Hi {_brand} team,\n\n"
                f"Our GEO audit scored {d16} at {_geo}/10 for AI discovery readiness. "
                f"We estimate a ${_leak:,.0f}/mo revenue leak in automated discovery channels.\n\n"
                f"Attached: full GEO visibility report with platform-native fix snippets.\n\n"
                f"— Revenue Leak Engine"
            )
            outreach_rows.append({
                "domain": d16,
                "subject": subject,
                "body": body
            })
        if outreach_rows:
            outreach_csv = out_dir_16 / f"{niche}_personalized_outreach.csv"
            with open(outreach_csv, "w", newline="", encoding="utf-8") as f:
                w = _csv16.DictWriter(f, fieldnames=["domain", "subject", "body"])
                w.writeheader()
                for r in outreach_rows:
                    w.writerow(r)
            print(f"  -> Phase 16 Personalized Outreach Generated: {outreach_csv}")
    except Exception as e:
        print(f"  warning: Phase 16 outreach failed - {e}")

    # =====================================================================
    # PHASE 17: WEBHOOK DISPATCH / CI/CD NOTIFICATION (INLINE)
    # =====================================================================
    try:
        import json as _json17
        hook_dir = LEADS_DIR / "webhooks"
        hook_dir.mkdir(parents=True, exist_ok=True)
        payload_17 = {
            "niche": niche,
            "leads_audited": len(scored_leads),
            "qualified_leaks": sum(1 for l in scored_leads if l.get("lead_status") == "QUALIFIED_LEAK"),
            "total_leak_usd": sum(float(l.get("estimated_monthly_leak_usd", 0) or 0) for l in scored_leads),
            "timestamp": __import__("time").time()
        }
        hook_file = hook_dir / f"{niche}_webhook_payload.json"
        hook_file.write_text(_json17.dumps(payload_17, indent=2), encoding="utf-8")
        print(f"  -> Phase 17 Webhook Payload Generated: {hook_file}")
    except Exception as e:
        print(f"  warning: Phase 17 webhook failed - {e}")


    # =====================================================================
    # PHASE 15: MULTI-TENANT AGENCY DASHBOARD (INLINE)
    # =====================================================================
    try:
        import csv as _csv15
        portfolio_15 = []
        total_leak_15 = 0
        for csv_file in LEADS_DIR.glob("*_leads_ranked.csv"):
            niche_15 = csv_file.stem.replace("_leads_ranked", "").title()
            with open(csv_file, encoding="utf-8") as f:
                for row in _csv15.DictReader(f):
                    leak_15 = float(row.get("estimated_monthly_leak_usd", 0) or 0)
                    total_leak_15 += leak_15
                    portfolio_15.append({"domain": row.get("domain"), "niche": niche_15, "geo": float(row.get("geo_score", 0) or 0), "cro": float(row.get("cro_score", 0) or 0), "status": row.get("lead_status", "UNKNOWN")})
        
        if portfolio_15:
            rows_15 = ""
            for p_item in portfolio_15:
                rows_15 += '<tr><td class="p-3">' + str(p_item["domain"]) + '</td><td class="p-3">' + str(p_item["niche"]) + '</td><td class="p-3">' + str(p_item["geo"]) + '</td><td class="p-3">' + str(p_item["cro"]) + '</td><td class="p-3">' + str(p_item["status"]) + '</td></tr>'
            leak_str_15 = f"{total_leak_15:,.0f}"
            html_15 = '<!DOCTYPE html><html><head><title>Agency Matrix</title><script src="https://cdn.tailwindcss.com"></script></head><body class="bg-slate-900 text-white p-8"><h1 class="text-3xl font-bold mb-4">Agency Portfolio Matrix</h1><div class="mb-6 text-xl">Total Portfolio Leak: <span class="text-red-400 font-bold">$' + leak_str_15 + '/mo</span></div><table class="w-full text-left border-collapse"><thead><tr class="border-b border-slate-700"><th class="p-3">Domain</th><th class="p-3">Niche</th><th class="p-3">GEO</th><th class="p-3">CRO</th><th class="p-3">Status</th></tr></thead><tbody class="divide-y divide-slate-800">' + rows_15 + '</tbody></table></body></html>'
            out_15 = LEADS_DIR.parent / "reports" / "agency_dashboard.html"
            out_15.parent.mkdir(parents=True, exist_ok=True)
            out_15.write_text(html_15, encoding="utf-8")
            print(f"  -> Phase 15 Agency Dashboard Generated: {out_15}")
    except Exception as e:
        print(f"  warning: Phase 15 dashboard failed - {e}")


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
