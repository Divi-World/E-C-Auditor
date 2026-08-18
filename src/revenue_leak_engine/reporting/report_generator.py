"""
Report generation + opportunity scoring (COMPLETE FILE).
Renders the client-ready HTML report with screenshots embedded as base64,
confidence tags, and the professional fix text carried by each issue.
"""
import base64
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from revenue_leak_engine.config import REPORTS_DIR, YOUR_NAME, YOUR_COMPANY

SEVERITY_POINTS = {"high": 3, "medium": 2, "low": 1}
SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}

TEMPLATES_DIR = Path(__file__).parent / "templates"


def opportunity_score(findings: dict) -> int:
    score = sum(SEVERITY_POINTS.get(i.get("severity"), 0)
                for i in findings.get("issues", []))
    return min(10, score)


def _b64(path) -> str | None:
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        return None
    try:
        return "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()
    except Exception:
        return None


def generate_report(findings: dict) -> str:
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)
    template = env.get_template("report.html")

    issues = sorted(findings.get("issues", []),
                    key=lambda i: SEVERITY_ORDER.get(i.get("severity"), 3))

    html = template.render(
        domain=findings["domain"],
        product_url=findings.get("product_url"),
        load_time_ms=findings.get("load_time_ms"),
        score=opportunity_score(findings),
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        issues=issues,
        notes=findings.get("notes", ""),
        screenshot_b64=_b64(findings.get("screenshot_path")),
        popup_b64=_b64(findings.get("popup_screenshot_path")),
        your_name=YOUR_NAME,
        your_company=YOUR_COMPANY,
    )

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS_DIR / f"{findings['domain'].replace('.', '_')}.html"
    out_path.write_text(html, encoding="utf-8")
    return str(out_path)