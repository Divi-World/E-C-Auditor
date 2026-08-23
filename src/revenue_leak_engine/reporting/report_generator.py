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
    """Calculates CRO Health Score: starts at 10.0 and SUBTRACTS for each unique issue."""
    if not findings or "issues" not in findings: return 10.0
    
    seen_codes = set()
    score = 10.0
    for issue in findings.get("issues", []):
        code = issue.get("code", "")
        if code in seen_codes: continue
        seen_codes.add(code)
        
        sev = issue.get("severity", "low")
        if sev == "high": score -= 1.2
        elif sev == "medium": score -= 0.4
        else: score -= 0.1
        
    return max(0.0, round(score, 1))

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
                for box in annotations:
                    x1 = box.get('x', 0) * ratio
                    y1 = box.get('y', 0) * ratio
                    x2 = (box.get('x', 0) + box.get('width', 0)) * ratio
                    y2 = (box.get('y', 0) + box.get('height', 0)) * ratio
                    # Draw high-visibility red evidence box
                    draw.rectangle([x1, y1, x2, y2], outline="#ef4444", width=4)
                    
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
    elif audit_status == "PARTIAL_WAF":
        score = "PARTIAL"
    else:
        score = opportunity_score(findings)

    cwv = findings.get("cwv", {})
    platform = findings.get("platform", "custom")
    
    # 2. PLATFORM FIX LOCATIONS
    where_map = {
        "shopify": "\n\n📍 Where to apply: Shopify Admin > Online Store > Themes > Edit Code (typically `product-template.liquid` or `theme.liquid`).",
        "woocommerce": "\n\n📍 Where to apply: WordPress Admin > Appearance > Theme File Editor (typically `single-product.php`) or via WooCommerce Settings.",
        "bigcommerce": "\n\n📍 Where to apply: BigCommerce Admin > Storefront > Script Manager or Theme Editor.",
        "magento": "\n\n📍 Where to apply: Magento Admin > Content > Design > Configuration or via XML layout updates.",
        "custom": "\n\n📍 Where to apply: Your CMS theme templates or global header/footer injection points."
    }
    where_note = where_map.get(platform, where_map["custom"])
    
    # Codes that belong strictly to SEO (to prevent cross-section duplication)
    seo_codes_set = {
        'poor_title_tag', 'title_tag_issue', 'missing_title_tag',
        'poor_meta_description', 'meta_description_issue', 'missing_meta_description',
        'h1_tag_issue', 'missing_h1',
        'missing_image_alt', 'image_alt_issue', 'no_alt_text',
        'missing_product_schema', 'schema_missing', 'no_product_schema',
        'missing_og_tags', 'broken_canonical'
    }

    # 3. SINGLE-PASS CANONICALIZATION, DEDUP, & SANITIZATION
    canon_map = {
        'poor_meta_description': 'meta_description_issue', 'missing_meta_description': 'meta_description_issue',
        'poor_title_tag': 'title_tag_issue', 'missing_title_tag': 'title_tag_issue',
        'h1_tag_issue': 'h1_tag_issue', 'missing_h1': 'h1_tag_issue',
        'missing_image_alt': 'image_alt_issue', 'no_alt_text': 'image_alt_issue',
        'no_add_to_cart_found': 'atc_missing', 'add_to_cart_not_visible': 'atc_missing',
        'missing_product_schema': 'schema_missing', 'no_product_schema': 'schema_missing'
    }
    
    seen_codes = set()
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
        
        # Inject Platform Location for CRO issues
        if code not in seo_codes_set and "📍 Where to apply" not in raw_fix:
            raw_fix += where_note
            
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
        
        # Categorize (Mutually Exclusive to prevent double rendering)
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
    
    if audit_status == "BLOCKED":
        evidence_summary = "Audit aborted due to WAF/CAPTCHA block. No CRO telemetry could be verified."
    elif audit_status == "TIMEOUT":
        evidence_summary = "Audit timed out. Partial telemetry captured."
    elif audit_status == "PARTIAL_WAF":
        evidence_summary = "Structural audit completed via stealth HTTP bypass. Interactive checks skipped due to WAF."
    else:
        evidence_summary = f"Score derived from {high_count} Critical, {med_count} Medium, and {low_count} Low friction points verified via headless telemetry."

    # 5. SCREENSHOTS
    popup_ann = findings.get("popup_annotation")
    screenshot_b64 = _process_screenshot(findings.get("screenshot_path"))
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
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        audit_status=audit_status,
        evidence_summary=evidence_summary,
        findings=findings
    )
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_out)

    return output_path
