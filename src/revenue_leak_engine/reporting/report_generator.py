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
    if not findings or "issues" not in findings:
        return 0.0
    score = 0.0
    for issue in findings.get("issues", []):
        sev = issue.get("severity", "low")
        if sev == "high":
            score += 2.0
        elif sev == "medium":
            score += 1.0
        else:
            score += 0.5
    if any(i.get("code") == "no_add_to_cart_found" for i in findings.get("issues", [])):
        score = max(score, 8.0)
    return min(10.0, round(score, 1))

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
    score = opportunity_score(findings)
    cwv = findings.get("cwv", {})
    
    high_issues = [i for i in findings.get("issues", []) if i.get("severity") == "high"]
    med_issues = [i for i in findings.get("issues", []) if i.get("severity") == "medium"]
    low_issues = [i for i in findings.get("issues", []) if i.get("severity") == "low"]
    
    popup_ann = findings.get("popup_annotation")
    screenshot_b64 = _process_screenshot(findings.get("screenshot_path"))
    # INDUSTRIAL PRINCIPLE: Only show popup screenshot if it is an active finding
    popup_b64 = None
    has_popup_finding = any(i.get("code") == "intrusive_popup" for i in findings.get("issues", []))
    if has_popup_finding:
        popup_b64 = _process_screenshot(findings.get("popup_screenshot_path"), popup_ann)
    
    seo_codes = ['poor_title_tag', 'poor_meta_description', 'h1_tag_issue', 'missing_image_alt']
    seo_issues = [i for i in findings.get("issues", []) if i.get("code") in seo_codes]
    
    html_out = template.render(
        domain=domain, score=score, load_time=findings.get("load_time_ms", "N/A"),
        lcp=cwv.get("lcp", 0), cls=cwv.get("cls", 0),
        product_url=findings.get("product_url", "N/A"),
        high_issues=high_issues, med_issues=med_issues, low_issues=low_issues,
        seo_issues=seo_issues, platform=findings.get("platform", "custom"),
        notes=findings.get("notes", ""), error=findings.get("error"),
        screenshot_b64=screenshot_b64, popup_b64=popup_b64,
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    )
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_out)
        
    return output_path
