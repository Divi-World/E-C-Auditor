import os

gen_code = """from datetime import datetime, timezone
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
"""

html_code = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>GEO & Agentic Commerce Audit: {{ domain }}</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #333; max-width: 900px; margin: 0 auto; padding: 40px 20px; background: #f9fafb; }
        .header { border-bottom: 3px solid #2563eb; padding-bottom: 20px; margin-bottom: 30px; }
        h1 { color: #111827; margin: 0; font-size: 2.2em; }
        h2 { color: #1f2937; border-bottom: 1px solid #e5e7eb; padding-bottom: 8px; margin-top: 40px; }
        .meta { color: #6b7280; font-size: 0.95em; margin-top: 8px; }
        .score-badge { display: inline-block; background: #2563eb; color: white; padding: 8px 16px; border-radius: 8px; font-size: 1.5em; font-weight: bold; margin-top: 10px; }
        .dimensions { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 16px; margin: 20px 0; }
        .dim-card { background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; text-align: center; }
        .dim-title { font-size: 0.85em; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px; }
        .dim-score { font-size: 1.8em; font-weight: bold; color: #111827; }
        .issue-card { background: white; border-left: 5px solid #ef4444; border-radius: 4px; padding: 20px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
        .issue-card.medium { border-left-color: #f59e0b; }
        .issue-card.low { border-left-color: #3b82f6; }
        .issue-title { font-size: 1.2em; font-weight: 600; color: #111827; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; }
        .badge { font-size: 0.75em; padding: 4px 10px; border-radius: 99px; font-weight: 600; text-transform: uppercase; }
        .badge.high { background: #fee2e2; color: #991b1b; }
        .badge.medium { background: #fef3c7; color: #92400e; }
        .badge.low { background: #dbeafe; color: #1e40af; }
        .evidence { background: #f3f4f6; padding: 12px; border-radius: 4px; font-family: monospace; font-size: 0.9em; color: #4b5563; margin: 12px 0; }
        .detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 12px; }
        .detail-box { background: #f9fafb; padding: 12px; border-radius: 4px; border: 1px solid #e5e7eb; }
        .detail-label { font-size: 0.75em; text-transform: uppercase; color: #6b7280; font-weight: 600; margin-bottom: 4px; }
        .notes { background: #ecfdf5; border: 1px solid #a7f3d0; padding: 16px; border-radius: 8px; margin-top: 20px; color: #065f46; }
        .footer { margin-top: 60px; text-align: center; font-size: 0.85em; color: #9ca3af; border-top: 1px solid #e5e7eb; padding-top: 20px; }
    </style>
</head>
<body>
    <div class="header">
        <h1>{{ domain }}</h1>
        <div class="meta">Enterprise GEO & Agentic Commerce Audit | Generated {{ generated_at }}</div>
        <div class="score-badge">Overall Readiness: {{ score }}/10</div>
    </div>
    <h2>Dimensional Readiness Matrix</h2>
    <div class="dimensions">
        {% for key, val in dimensions.items() %}
        <div class="dim-card">
            <div class="dim-title">{{ key | replace('_', ' ') | title }}</div>
            <div class="dim-score">{{ val }}</div>
        </div>
        {% endfor %}
    </div>
    {% if notes %}
    <div class="notes"><strong>Executive Notes:</strong> {{ notes }}</div>
    {% endif %}
    <h2>Detailed Findings & Business Impact</h2>
    {% if issues %}
        {% for issue in issues %}
        <div class="issue-card {{ issue.severity }}">
            <div class="issue-title">
                <span>{{ issue.description }}</span>
                <span class="badge {{ issue.severity }}">{{ issue.severity }} severity</span>
            </div>
            <div class="evidence"><strong>Evidence:</strong> {{ issue.evidence }}</div>
            <p><strong>Business Impact:</strong> {{ issue.business_impact }}</p>
            <div class="detail-grid">
                <div class="detail-box"><div class="detail-label">Implementation Difficulty</div><div>{{ issue.difficulty }}</div></div>
                <div class="detail-box"><div class="detail-label">Confidence Level</div><div>{{ issue.confidence | title }}</div></div>
            </div>
            <p style="margin-top: 16px; color: #2563eb;"><strong>Recommended Fix:</strong> {{ issue.fix }}</p>
        </div>
        {% endfor %}
    {% else %}
        <p style="background: #ecfdf5; padding: 20px; border-radius: 8px; text-align: center; color: #065f46;">No critical GEO or Agentic Commerce leaks detected. The site is fully optimized for AI engines.</p>
    {% endif %}
    <div class="footer">Generated by Revenue Leak Engine v5.0 Enterprise | Powered by {{ your_company }}</div>
</body>
</html>"""

with open('src/revenue_leak_engine/reporting/geo_report_generator.py', 'w', encoding='utf-8') as f:
    f.write(gen_code)

os.makedirs('src/revenue_leak_engine/reporting/templates', exist_ok=True)
with open('src/revenue_leak_engine/reporting/templates/geo_report.html', 'w', encoding='utf-8') as f:
    f.write(html_code)

print("Enterprise UI & Generator successfully deployed.")
