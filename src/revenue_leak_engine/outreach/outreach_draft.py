"""
Outreach draft generation (COMPLETE FILE).
Picks the single most severe HIGH-confidence issue and writes a short,
quantified, human-sounding draft. Never sends anything.
"""
import csv
from revenue_leak_engine.config import LOGS_DIR, YOUR_NAME, YOUR_COMPANY

SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}
CONF_RANK = {"high": 0, "medium": 1, "low": 2}


def top_issue(findings: dict) -> dict | None:
    issues = findings.get("issues", [])
    if not issues:
        return None
    return sorted(issues, key=lambda i: (
        CONF_RANK.get(i.get("confidence", "high"), 3),
        SEVERITY_RANK.get(i["severity"], 9),
    ))[0]


def _hook(findings: dict, issue: dict) -> str:
    domain = findings["domain"]
    ms = findings.get("load_time_ms") or 0
    code = issue["code"]
    if code == "slow_load":
        sec = round(ms / 1000, 1)
        return (f"I ran a mobile audit of {domain}'s product page and measured a "
                f"{sec}-second load time. Every second above ~2.5s typically costs "
                f"8-12% of mobile conversions.")
    if code in ("add_to_cart_below_fold", "add_to_cart_not_visible", "no_add_to_cart_found"):
        return (f"I checked {domain} on a real mobile viewport and the Add to Cart "
                f"button is not visible above the fold — shoppers have to scroll to "
                f"find the buy button.")
    if code == "no_express_checkout":
        return (f"I went through {domain}'s mobile checkout flow and there's no "
                f"Shop Pay / Apple Pay express option on the product page or cart — "
                f"that's extra friction for impulse buyers.")
    if code == "intrusive_popup":
        return (f"On mobile, {domain} greets visitors with a full-screen popup "
                f"before they can even see the product — that blocks the buy path "
                f"on first view.")
    if code == "add_to_cart_event_missing":
        return (f"{domain} has pixels installed, but clicking Add to Cart fired no "
                f"tracking event in my test — so your ad platforms can't optimize "
                f"toward purchase intent.")
    return f"I was checking out {domain} on mobile and noticed: {issue['description']}"


# ---------- GEO-specific hooks and draft function ----------
def _geo_hook(geo_findings: dict, issue: dict) -> str:
    domain = geo_findings["domain"]
    code = issue["code"]

    # Professional B2B E-commerce Hooks (Zero "AI Discovery" skepticism)
    hooks = {
        "ai_crawlers_blocked": f"I reviewed {domain}'s routing directives (robots.txt) and noticed automated indexing agents are currently restricted. This limits your catalog's visibility in next-generation search environments.",
        "missing_faq_schema": f"While analyzing {domain}'s structured data layer, I noticed a gap in your definitional markup. This directly impacts how automated search systems extract and cite your commercial policies.",
        "missing_organization_entity": f"{domain} is currently missing unified Organization markup. This fragments your brand entity graph, reducing the confidence automated systems have when attributing your products in search results.",
        "incomplete_product_schema": f"I ran a structural telemetry check on {domain}'s product pages and found incomplete machine-readable commerce data. Without verified pricing and inventory schemas, automated shopping systems cannot accurately process your catalog.",
        "redirect_shell_detected": f"I noticed {domain} routes core merchandising pages to external checkout shells without preserving structured data. This severs the data chain for automated parsers before they can index your catalog.",
        "csr_schema_leak": f"{domain} is rendering critical product schema exclusively via client-side JavaScript. Lightweight automated parsers that don't execute scripts are seeing an empty catalog.",
        "crawlability_unmeasured": f"{domain}'s security gateway is aggressively filtering automated indexing requests. This is preventing next-gen search parsers from accessing your catalog and policy files.",
        "agentic_commerce_partial": f"{domain} has the foundational discovery files in place, but the API handshake for catalog and transaction tools is failing. Automated agents can locate your brand but cannot process transactions."
    }

    return hooks.get(code, f"I ran a structural telemetry audit on {domain} and identified a critical gap in your machine-readable commerce data: {issue['description']}")


def draft_geo_email(geo_findings: dict, report_url: str = "") -> dict:
    domain = geo_findings["domain"]
    issue = top_issue(geo_findings)

    if not issue:
        return {"domain": domain, "subject": None, "body": None,
                "note": "Healthy GEO profile - skipped."}

    subject = f"Merchandising Visibility & Structured Data Telemetry: {domain}"
    body = (
        f"Hi Team,\n\n"
        f"{_geo_hook(geo_findings, issue)}\n\n"
        f"As search behavior shifts toward automated, conversational, and machine-parsed environments, "
        f"maintaining rigorous structured commerce data is critical for protecting market share. "
        f"I've compiled a brief telemetry report detailing these gaps, including the exact implementation "
        f"paths and code snippets your engineering team needs to resolve them natively.\n\n"
        f"Are you open to reviewing the interactive report?\n\n"
        f"Best,\n"
        f"{YOUR_NAME or '[Your Name]'}"
        f"{(' | ' + YOUR_COMPANY) if YOUR_COMPANY else ''}\n"
        f"(Reply STOP to opt out.)"
    )

    return {
        "domain": domain,
        "subject": subject,
        "body": body,
        "referenced_issue": issue["code"],
        "report_url": report_url,
        "note": "DRAFT ONLY — review, personalize, and send manually.",
    }
# ----------------------------------------------------------------


def draft_email(findings: dict, report_url: str = "") -> dict:
    """Phase J: Hyper-Personalized Enterprise Outreach Draft"""
    domain = findings.get("domain", "unknown")
    from revenue_leak_engine.reporting.report_generator import opportunity_score
    score = opportunity_score(findings)
    priority = "HIGH" if score < 5.0 else ("MEDIUM" if score < 7.5 else "LOW")
    ttfb = findings.get("ttfb_ms", 0)
    tech_stack = findings.get("tech_stack", [])
    high_issues = [i for i in findings.get("issues", []) if i.get("severity") == "high"]
    top_issue_obj = high_issues[0] if high_issues else None
    top_issue_desc = top_issue_obj.get("description", "critical conversion friction") if top_issue_obj else "critical conversion friction"
    top_issue_code = top_issue_obj.get("code", "general_friction") if top_issue_obj else "general_friction"
    subject = f"CRO Health Audit: {domain} ({score}/10 - Priority: {priority})"
    NL = chr(10)
    body = f"Hi Team,{NL}{NL}"
    body += f"I was reviewing {domain}'s mobile checkout flow and ran a headless telemetry audit to benchmark your CRO Health against industry standards.{NL}{NL}"
    body += f"Your current CRO Health Score is {score}/10 (Priority: {priority}).{NL}{NL}"
    if ttfb is not None and ttfb > 800:
        body += f"1. Server Health (TTFB): Your Time to First Byte is {ttfb}ms. This indicates your hosting infrastructure is bottlenecking the frontend before the user even sees the page.{NL}"
    elif high_issues:
        body += f"1. Primary Leak: {top_issue_desc}.{NL}"
    if tech_stack:
        stack_str = ", ".join(tech_stack[:3])
        body += f"{NL}I also noticed you're running an advanced stack ({stack_str}), which means your engineering team is more than capable of implementing these fixes quickly.{NL}"
    body += f"{NL}I've generated a full interactive report with the exact DOM evidence and platform-specific code snippets to resolve these leaks.{NL}{NL}"
    body += f"Report: {report_url}{NL}{NL}"
    body += f"Are you open to a brief 10-minute walkthrough of the telemetry data this week?{NL}{NL}"
    name = YOUR_NAME or "[Your Name]"
    company = YOUR_COMPANY or "Enterprise Revenue Intelligence"
    body += f"Best,{NL}{name}{NL}{company}"
    return {
        "domain": domain,
        "subject": subject,
        "body": body,
        "referenced_issue": top_issue_code,
        "report_url": report_url,
        "note": "DRAFT ONLY - review, personalize, and send manually.",
    }


def append_draft_to_log(draft: dict):
    if not draft.get("subject"):
        return
    log_path = LOGS_DIR / "outreach_drafts.csv"
    write_header = not log_path.exists()
    with open(log_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "domain", "subject", "body", "referenced_issue", "report_url", "note"
        ])
        if write_header:
            writer.writeheader()
        writer.writerow({k: draft.get(k, "") for k in writer.fieldnames})
