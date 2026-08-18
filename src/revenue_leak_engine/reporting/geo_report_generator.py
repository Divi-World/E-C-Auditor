from datetime import datetime, timezone
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from revenue_leak_engine.config import REPORTS_DIR, YOUR_NAME, YOUR_COMPANY

TEMPLATES_DIR = Path(__file__).parent / "templates"

def generate_geo_report(geo_findings: dict) -> str:
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)
    template = env.get_template("geo_report.html")
    from revenue_leak_engine.audit.geo_audit import geo_opportunity_score

    issues = sorted(geo_findings.get("issues", []),
                    key=lambda i: {"high": 0, "medium": 1, "low": 2}.get(i.get("severity"), 3))

    html = template.render(
        domain=geo_findings["domain"],
        score=geo_opportunity_score(geo_findings),
        dimensions=geo_findings.get("dimensions", {}),
        dimensions_measured=geo_findings.get("dimensions_measured", {}),
        platform_detected=geo_findings.get("platform_detected", "unknown"),
        score_confidence=geo_findings.get("score_confidence", "partial"),
        crawlability_matrix=geo_findings.get("crawlability_matrix", {}),
        agentic_capabilities=geo_findings.get("agentic_capabilities", {}),
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        issues=issues,
        notes=geo_findings.get("notes", ""),
        your_name=YOUR_NAME,
        your_company=YOUR_COMPANY,
    )

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS_DIR / f"{geo_findings['domain'].replace('.', '_')}_geo.html"
    out_path.write_text(html, encoding="utf-8")
    return str(out_path)
