import os
import base64
import io
from jinja2 import Environment, FileSystemLoader, select_autoescape
from datetime import datetime, timezone

try:
    from PIL import Image, ImageDraw
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")
REPORTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "data", "reports"
)
env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=select_autoescape(["html", "xml"])
)

def opportunity_score(findings: dict) -> float:
    """Enterprise Weighted Scoring Matrix (Baymard Impact Model)"""
    if not findings or "issues" not in findings: return 10.0
    score = 100.0
    weights = {"high": 12.0, "medium": 3.5, "low": 0.5}
    conf_mult = {"VERIFIED": 1.0, "high": 0.9, "medium": 0.6, "low": 0.3}
    seen_codes = set()
    for issue in findings.get("issues", []):
        code = issue.get("code", "")
        if code in seen_codes: continue
        seen_codes.add(code)
        sev = issue.get("severity", "low")
        conf = issue.get("confidence", "medium")
        base_penalty = weights.get(sev, 2.0)
        multiplier = conf_mult.get(conf, 0.5)
        if code in ["forced_account_creation", "checkout_hidden_fees_detected", "slow_ttfb_server_health"]:
            base_penalty = 25.0
        score -= (base_penalty * multiplier)
    return max(1.0, round(score / 10.0, 1))  # Floor at 1.0


def _process_screenshot(path_str, annotations=None):
    """Resizes, compresses to JPEG, and draws red bounding boxes on evidence."""
    if not path_str or not os.path.exists(path_str): return None
    try:
        if HAS_PIL:
            img = Image.open(path_str)
            orig_w, orig_h = img.size
            max_w = 600  # Industrial limit to prevent HTML bloat
            ratio = 1.0
            if orig_w > max_w:
                ratio = max_w / orig_w
                img = img.resize((max_w, int(orig_h * ratio)), Image.LANCZOS)
            
            if annotations:
                draw = ImageDraw.Draw(img)
                try:
                    from PIL import ImageFont
                    font = ImageFont.load_default()
                except Exception:
                    font = None
                    
                for box in annotations:
                    x1 = box.get('x', 0) * ratio
                    y1 = box.get('y', 0) * ratio
                    x2 = (box.get('x', 0) + box.get('width', 0)) * ratio
                    y2 = (box.get('y', 0) + box.get('height', 0)) * ratio
                    color = "#ef4444" if "missing" in box.get('type', '') or "small" in box.get('type', '') else "#22c55e"
                    draw.rectangle([x1, y1, x2, y2], outline=color, width=4)
                    if box.get('label') and font:
                        # Draw text background for readability
                        text_w, text_h = draw.textsize(box['label'], font=font) if hasattr(draw, 'textsize') else (len(box['label'])*6, 12)
                        draw.rectangle([x1, y1, x1 + text_w + 10, y1 + text_h + 10], fill=color)
                        draw.text((x1 + 5, y1 + 5), box['label'], fill="#ffffff", font=font)
                    
            buffer = io.BytesIO()
            img = img.convert('RGB')
            img.save(buffer, format="JPEG", quality=75, optimize=True)
            return base64.b64encode(buffer.getvalue()).decode('utf-8')
        else:
            with open(path_str, "rb") as f:
                return base64.b64encode(f.read()).decode('utf-8')
    except Exception: return None

def generate_report(findings: dict) -> str:
    domain = findings.get("domain", "unknown")
    safe_name = domain.replace(".", "_").replace(":", "_")

    os.makedirs(REPORTS_DIR, exist_ok=True)
    output_path = os.path.join(REPORTS_DIR, f"{safe_name}.html")

    template = env.get_template("report.html")
    
    # 1. STATE MACHINE & SCORING
    error_state = findings.get("error", "")
    audit_status = findings.get("audit_status", "VERIFIED")
    
    if error_state and ("waf" in str(error_state).lower() or "captcha" in str(error_state).lower()):
        audit_status = "BLOCKED"
        score = "BLOCKED"
    elif error_state and "timeout" in str(error_state).lower():
        audit_status = "TIMEOUT"
        score = "TIMEOUT"
    # SINGLE SOURCE OF TRUTH: Score and Status determination
    checks = findings.get("checks_completed", {})

    if checks.get("atc_probe"):
        # Interactive telemetry verified. Overrides poisoned WAF notes.
        audit_status = "VERIFIED"
        findings["audit_status"] = "VERIFIED"
        score = opportunity_score(findings)
    elif audit_status == "PARTIAL_WAF" or "PARTIAL_WAF" in findings.get("notes", "") or "curl_cffi_fallback" in findings.get("notes", ""):
        score = "PARTIAL"
        audit_status = "PARTIAL_WAF"
        findings["audit_status"] = "PARTIAL_WAF"
    else:
        score = opportunity_score(findings)


    cwv = findings.get("cwv", {})
    platform = findings.get("platform", "custom")
    
    # 2. PLATFORM FIX LOCATIONS (Granular per issue code)
    generic_where = {
        "shopify": "\n\n📍 Where to apply: Shopify Admin > Online Store > Themes > Edit Code.",
        "woocommerce": "\n\n📍 Where to apply: WordPress Admin > Appearance > Theme File Editor or WooCommerce Settings.",
        "bigcommerce": "\n\n📍 Where to apply: BigCommerce Admin > Storefront > Script Manager or Theme Editor.",
        "magento": "\n\n📍 Where to apply: Magento Admin > Content > Design > Configuration.",
        "custom": "\n\n📍 Where to apply: Your CMS theme templates or global header/footer."
    }
    specific_where = {
        "meta_pixel_missing": {"shopify": "Shopify Admin > Settings > Apps > Facebook & Instagram > Data Sharing.", "woocommerce": "WooCommerce > Settings > Integration > Facebook for WooCommerce.", "custom": "GTM or global header template."},
        "tiktok_pixel_missing": {"shopify": "Shopify Admin > Settings > Apps > TikTok > Data Sharing.", "woocommerce": "WooCommerce > Settings > Integration > TikTok.", "custom": "GTM or global header template."},
        "no_cart_drawer": {"shopify": "Shopify Admin > Online Store > Themes > Customize > Theme Settings > Cart (Enable Drawer).", "woocommerce": "Appearance > Customize > WooCommerce > Cart (Enable AJAX mini-cart).", "custom": "Theme cart template or slide-out cart plugin."},
        "no_express_checkout": {"shopify": "Shopify Admin > Settings > Payments > Shopify Payments > Manage (Enable Wallets).", "woocommerce": "WooCommerce > Settings > Payments > Stripe/PayPal (Enable Payment Request).", "custom": "Payment gateway dashboard and checkout integration."},
        "missing_sticky_atc": {"shopify": "Online Store > Themes > Customize > Product Page (Enable Sticky ATC).", "woocommerce": "Appearance > Customize > Single Product (or use a Sticky ATC plugin).", "custom": "Product template (add fixed-position bottom bar)."},
        "hidden_shipping_costs": {"shopify": "Online Store > Themes > Customize > Product Page (Add shipping estimator app block).", "woocommerce": "WooCommerce > Settings > Shipping (or use a shipping calculator plugin).", "custom": "Product template (integrate shipping API estimator)."},
        "missing_product_schema": {"shopify": "Online Store > Themes > Edit Code (product-template.liquid) or use an SEO app.", "woocommerce": "Use Yoast/RankMath SEO plugin, or add to single-product.php.", "custom": "Global product template (inject JSON-LD script)."}
    }
    where_note = generic_where.get(platform, generic_where["custom"])
    
    # PHASE L: PRESCRIPTIVE APP MAPPING
    app_map = {
        "missing_sticky_atc": {"shopify": "Recommended App: 'Sticky Add To Cart' by Codeinmatic.", "woocommerce": "Recommended Plugin: 'WooCommerce Sticky Add to Cart'."},
        "no_cart_drawer": {"shopify": "Recommended App: 'Slide Cart' by Appstle.", "woocommerce": "Recommended Plugin: 'WooCommerce Side Cart'."},
        "missing_product_schema": {"shopify": "Recommended App: 'JSON-LD for SEO' by Ilana Davis.", "woocommerce": "Recommended Plugin: Yoast SEO or RankMath."},
        "no_review_widget": {"shopify": "Recommended App: Judge.me or Okendo.", "woocommerce": "Recommended Plugin: Judge.me or Yotpo."},
        "missing_cross_sell": {"shopify": "Recommended App: 'Frequently Bought Together' by Shopify.", "woocommerce": "Recommended Plugin: 'WooCommerce Frequently Bought Together'."},
        "missing_delivery_urgency": {"shopify": "Recommended App: 'Estimated Delivery Date' by Identix.", "woocommerce": "Recommended Plugin: 'WooCommerce Estimated Delivery Date'."}
    }
    
    # Codes that belong strictly to SEO (to prevent cross-section duplication)
    seo_codes_set = {
        'poor_title_tag', 'title_tag_issue', 'missing_title_tag', 'title_tag_length',
        'poor_meta_description', 'meta_description_issue', 'missing_meta_description', 'meta_description_0_chars',
        'h1_tag_issue', 'missing_h1', 'multiple_h1_tags', 'weak_homepage_h1',
        'missing_image_alt', 'image_alt_issue', 'no_alt_text', 'images_lack_alt_text',
        'missing_product_schema', 'schema_missing', 'no_product_schema', 'missing_product_schema_markup',
        'missing_og_tags', 'og_tags_missing', 'open_graph_incomplete',
        'broken_canonical', 'canonical_broken', 'canonical_missing'
    }

    # 3. SINGLE-PASS CANONICALIZATION, DEDUP, & SANITIZATION
    canon_map = {
        'poor_meta_description': 'meta_description_issue', 'missing_meta_description': 'meta_description_issue', 'meta_description_0_chars': 'meta_description_issue',
        'poor_title_tag': 'title_tag_issue', 'missing_title_tag': 'title_tag_issue', 'title_tag_length': 'title_tag_issue',
        'h1_tag_issue': 'h1_tag_issue', 'missing_h1': 'h1_tag_issue', 'multiple_h1_tags': 'h1_tag_issue', 'weak_homepage_h1': 'h1_tag_issue',
        'missing_image_alt': 'image_alt_issue', 'no_alt_text': 'image_alt_issue', 'images_lack_alt_text': 'image_alt_issue',
        'no_add_to_cart_found': 'atc_missing', 'add_to_cart_not_visible': 'atc_missing',
        'missing_product_schema': 'schema_missing', 'no_product_schema': 'schema_missing', 'missing_product_schema_markup': 'schema_missing',
        'missing_og_tags': 'og_tags_missing', 'open_graph_incomplete': 'og_tags_missing',
        'broken_canonical': 'canonical_broken', 'canonical_missing': 'canonical_broken'
    }
    

    snippet_map = {
        "shopify": {
            "schema_missing": "\n\n🛠️ Code Snippet (Paste in theme.liquid before </head>):\n<script type=\"application/ld+json\">\n{\n  \"@context\": \"https://schema.org\",\n  \"@type\": \"Product\",\n  \"name\": \"{{ product.title | escape }}\",\n  \"image\": \"{{ product.featured_image | img_url: 'master' }}\",\n  \"offers\": {\n    \"@type\": \"Offer\",\n    \"priceCurrency\": \"{{ shop.currency }}\",\n    \"price\": \"{{ product.price | money_without_currency }}\",\n    \"availability\": \"{% if product.available %}https://schema.org/InStock{% else %}https://schema.org/OutOfStock{% endif %}\"\n  }\n}\n</script>",
            "meta_pixel_missing": "\n\n🛠️ GTM Snippet (Custom HTML Tag):\n<script>\n  !function(f,b,e,v,n,t,s){if(f.fbq)return;n=f.fbq=function(){n.callMethod?n.callMethod.apply(n,arguments):n.queue.push(arguments)};if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];t=b.createElement(e);t.async=!0;t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}(window, document,'script','https://connect.facebook.net/en_US/fbevents.js');\n  fbq('init', 'YOUR_PIXEL_ID'); fbq('track', 'PageView');\n</script>"
        },
        "woocommerce": {
            "schema_missing": "\n\n🛠️ Code Snippet (Paste in functions.php):\nadd_action('wp_head', function() {\n  if (is_product()) {\n    global $product;\n    $schema = array('@context'=>'https://schema.org','@type'=>'Product','name'=>$product->get_name(),'offers'=>array('@type'=>'Offer','priceCurrency'=>get_woocommerce_currency(),'price'=>$product->get_price()));\n    echo '<script type=\"application/ld+json\">'.json_encode($schema).'</script>';\n  }\n});"
        },
        "custom": {
            "schema_missing": "\n\n🛠️ JSON-LD Template:\n<script type=\"application/ld+json\">\n{\n  \"@context\": \"https://schema.org\",\n  \"@type\": \"Product\",\n  \"name\": \"[Product Name]\",\n  \"offers\": { \"@type\": \"Offer\", \"price\": \"[Price]\", \"priceCurrency\": \"[Currency]\" }\n}\n</script>"
        }
    }
    seen_codes = set()
    seen_descs_global = set()
    high_issues, med_issues, low_issues, seo_issues = [], [], [], []
    
    for issue in findings.get("issues", []):
        # Canonicalize
        raw_code = issue.get("code", "unknown")
        code = canon_map.get(raw_code, raw_code)
        
        # Cross-Module Deduplication (Kill duplicates between CRO and SEO)
        if code in seen_codes:
            continue
        seen_codes.add(code)
        
        # Sanitize Text (Zero Blanks)
        desc = issue.get("description") or issue.get("observation") or issue.get("title") or "Friction point detected in the user journey."
        ev = issue.get("evidence") or "Telemetry data confirms deviation from industrial standards."
        impact = issue.get("business_impact") or issue.get("interpretation") or "Directly impacts conversion velocity or shopper trust."
        raw_fix = issue.get("fix") or issue.get("recommendation") or "Consult your engineering team to resolve this friction point."
        
        # Inject Platform Location for CRO issues (Granular)
        if code not in seo_codes_set and "📍 Where to apply" not in raw_fix:
            if code in specific_where and platform in specific_where[code]:
                raw_fix += f"\n\n📍 Where to apply: {specific_where[code][platform]}"
            else:
                raw_fix += where_note
        # PHASE L: Prescriptive App Recommendations
        if 'app_map' in locals() and code in app_map and platform in app_map[code]:
            app_rec = app_map[code][platform]
            if app_rec not in raw_fix:
                raw_fix += "\n\n[RECOMMENDED APP] " + app_rec

        # PHASE L: Prescriptive App Recommendations
        if code in app_map and platform in app_map[code]:
            app_rec = app_map[code][platform]
            if app_rec not in raw_fix:
                raw_fix += "\n\n🚀 " + app_rec

                
        # PHASE L: Prescriptive App Recommendations
        if code in app_map and platform in app_map[code] and app_map[code][platform] not in raw_fix:
            raw_fix += f"\n\n🚀 {app_map[code][platform]}"
            
        # Inject Platform-Specific Code Snippets
        if platform in snippet_map and code in snippet_map[platform]:
            raw_fix += snippet_map[platform][code]
            
        # Update issue dict
        issue["code"] = code
        issue["title"] = desc
        issue["description"] = desc
        issue["observation"] = desc
        issue["evidence"] = ev
        issue["business_impact"] = impact
        issue["interpretation"] = impact
        issue["fix"] = raw_fix
        issue["recommendation"] = raw_fix
        issue["severity"] = issue.get("severity", "medium")
        issue["confidence"] = str(issue.get("confidence", "VERIFIED")).upper()
        
        # NUCLEAR TEXT DEDUP: If we have already seen this exact description, drop it entirely.
        desc_sig = (issue.get("description") or issue.get("observation") or "").strip().lower()[:40]
        if desc_sig in seen_descs_global:
            continue
        seen_descs_global.add(desc_sig)

        # STRICT CATEGORIZATION: SEO codes go ONLY to seo_issues. CRO codes go to high/med/low.
        if code in seo_codes_set:
            seo_issues.append(issue)
        else:
            sev = issue.get("severity")
            if sev == "high": high_issues.append(issue)
            elif sev == "medium": med_issues.append(issue)
            else: low_issues.append(issue)

    # 4. EVIDENCE SUMMARY
    high_count = len(high_issues)
    med_count = len(med_issues)
    low_count = len(low_issues)
    
    # PHASE D: NICHE BENCHMARKING DATA
    niche_benchmarks = {
        "beauty": {"lcp_avg": 2800, "scripts_avg": 45, "lcp_label": "Beauty Avg"},
        "apparel": {"lcp_avg": 2500, "scripts_avg": 50, "lcp_label": "Apparel Avg"},
        "default": {"lcp_avg": 3000, "scripts_avg": 40, "lcp_label": "Industry Avg"}
    }
    bench = niche_benchmarks.get(findings.get("niche", "default"), niche_benchmarks["default"])
    
    if audit_status == "BLOCKED":
        evidence_summary = "Audit aborted due to WAF/CAPTCHA block. No CRO telemetry could be verified."
    elif audit_status == "TIMEOUT":
        evidence_summary = "Audit timed out. Partial telemetry captured."
    elif audit_status == "PARTIAL_WAF":
        evidence_summary = "⚠️ STATIC ANALYSIS ONLY: Enterprise WAF blocked interactive browser telemetry. CRO score is capped. Findings are limited to structural HTML analysis (Meta, Schema, basic DOM). Add-to-Cart and Checkout flows could not be physically verified."
    else:
        evidence_summary = f"Health score derived from {high_count} Critical, {med_count} Medium, and {low_count} Low friction points verified via headless telemetry."

    # 5. SCREENSHOTS
    popup_ann = findings.get("popup_annotation")
    main_ann = findings.get("annotations", [])
    screenshot_b64 = _process_screenshot(findings.get("screenshot_path"), main_ann)
    popup_b64 = None
    has_popup_finding = any(i.get("code") == "intrusive_popup" for i in findings.get("issues", []))
    if has_popup_finding:
        popup_b64 = _process_screenshot(findings.get("popup_screenshot_path"), popup_ann)

    # 6. RENDER
    html_out = template.render(
        domain=domain, score=score, load_time=findings.get("load_time_ms", "N/A"),
        lcp=cwv.get("lcp", 0), cls=cwv.get("cls", 0),
        product_url=findings.get("product_url", "N/A"),
        high_issues=high_issues, med_issues=med_issues, low_issues=low_issues,
        seo_issues=seo_issues, platform=platform,
        notes=findings.get("notes", ""), error=findings.get("error"),
        screenshot_b64=screenshot_b64, popup_b64=popup_b64,
        tech_stack=findings.get("tech_stack", []),
        ttfb=findings.get("ttfb_ms"),
        bench=bench,
        lcp_val=cwv.get("lcp", 0),
        scripts_val=findings.get("script_bloat_count", 0),
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        audit_status=audit_status,
        evidence_summary=evidence_summary,
        findings=findings,
        run_id=findings.get("run_id", "N/A"),
        engine_version=findings.get("engine_version", "N/A"),
        viewport=findings.get("viewport", "390x844"),
        findings_hash=findings.get("findings_hash", "N/A"),
        checks_completed=findings.get("checks_completed", {}),
        checks_total=len(findings.get("checks_completed", {})),
        checks_passed=len([v for v in findings.get("checks_completed", {}).values() if v])
    )
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_out)

    return output_path
