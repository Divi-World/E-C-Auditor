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
    
    # Mapped exactly to the v8.3 Engine issue codes
    hooks = {
        "ai_crawlers_blocked": f"I checked {domain}'s robots.txt and it's currently blocking AI crawlers like GPTBot and ClaudeBot — meaning you're invisible in a growing share of AI product discovery.",
        "missing_faq_schema": f"I checked how AI search engines see {domain} and there's no FAQ structured data on the site — that's the single strongest signal for getting quoted directly in ChatGPT/Perplexity answers, and it's missing.",
        "missing_organization_entity": f"{domain} is missing Organization schema, which weakens how confidently AI systems can identify and attribute the brand in answers.",
        "incomplete_product_schema": f"I audited {domain}'s product pages and the schema is incomplete — AI shopping agents can't verify your live inventory or pricing, leading to abandoned machine-checkouts.",
        "redirect_shell_detected": f"I noticed {domain} redirects core merchandising pages to external checkout shells without schema, which blinds AI agents before they can even see your catalog.",
        "csr_schema_leak": f"{domain} is hiding its product schema behind Client-Side Rendering. Lightweight AI shopping agents that don't execute JavaScript see 0% of your catalog data.",
        "crawlability_unmeasured": f"{domain}'s aggressive WAF is blocking AI discovery files (like llms.txt and agents.md), which prevents next-gen shopping agents from understanding your catalog policies.",
        "agentic_commerce_partial": f"{domain} has the UCP discovery file, but the MCP handshake for catalog and cart tools is failing — AI agents can find you but can't transact."
    }
    
    return hooks.get(code, f"I audited {domain} for AI-search visibility and noticed: {issue['description']}")


def draft_geo_email(geo_findings: dict, report_url: str = "") -> dict:
    domain = geo_findings["domain"]
    issue = top_issue(geo_findings)

    if not issue:
        return {"domain": domain, "subject": None, "body": None,
                "note": "Healthy GEO profile - skipped."}

    subject = f"{domain} is invisible to AI search — quick fix"
    body = (
        f"Hi,\n\n"
        f"{_geo_hook(geo_findings, issue)}\n\n"
        f"As more shoppers ask ChatGPT/Perplexity/Google AI Overviews for "
        f"recommendations instead of googling, this directly affects discovery. "
        f"I put together a short breakdown of what's missing, and I've even included "
        f"the exact JSON-LD code snippet your developer needs to paste in to fix it.\n\n"
        f"Mind if I send the link over?\n\n"
        f"{YOUR_NAME or '[Your name]'}"
        f"{' — ' + YOUR_COMPANY if YOUR_COMPANY else ''}\n"
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
    if ttfb and ttfb > 800:
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
