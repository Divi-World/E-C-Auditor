import os
from jinja2 import Environment, FileSystemLoader, select_autoescape
from datetime import datetime, timezone

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")
env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=select_autoescape(["html", "xml"])
)

def opportunity_score(findings: dict) -> float:
    if not findings or "issues" not in findings: return 10.0
    score = 10.0
    for issue in findings.get("issues", []):
        sev = issue.get("severity", "low")
        if sev == "high": score -= 2.0
        elif sev == "medium": score -= 1.0
        else: score -= 0.5
    if any(i.get("code") == "no_add_to_cart_found" for i in findings.get("issues", [])):
        score = min(score, 2.0)
    return max(0.0, round(score, 1))

def generate_report(findings: dict) -> str:
    domain = findings.get("domain", "unknown")
    safe_name = domain.replace(".", "_").replace(":", "_")
    
    # Determine output directory (data/reports relative to project root)
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    reports_dir = os.path.join(base_dir, "data", "reports")
    os.makedirs(reports_dir, exist_ok=True)
    output_path = os.path.join(reports_dir, f"{safe_name}.html")

    template = env.get_template("report.html")
    score = opportunity_score(findings)
    cwv = findings.get("cwv", {})
    
    high_issues = [i for i in findings.get("issues", []) if i.get("severity") == "high"]
    med_issues = [i for i in findings.get("issues", []) if i.get("severity") == "medium"]
    low_issues = [i for i in findings.get("issues", []) if i.get("severity") == "low"]
    
    html_out = template.render(
        domain=domain, score=score, load_time=findings.get("load_time_ms", "N/A"),
        lcp=cwv.get("lcp", 0), cls=cwv.get("cls", 0),
        product_url=findings.get("product_url", "N/A"),
        high_issues=high_issues, med_issues=med_issues, low_issues=low_issues,
        notes=findings.get("notes", ""), error=findings.get("error"),
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    )
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_out)
        
    return output_path
