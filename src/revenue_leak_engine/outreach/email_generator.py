def generate_outreach_email(findings: dict) -> str:
    """
    Generates a highly personalized, evidence-backed cold outreach email.
    """
    domain = findings.get("domain", "prospect")
    platform = findings.get("platform", "custom").capitalize()
    leak_monthly = findings.get("estimated_monthly_leak_usd", 0)
    leak_annual = findings.get("estimated_annual_leak_usd", 0)
    tech_stack = findings.get("tech_stack", [])
    issues = findings.get("issues", [])
    
    # Filter for high/medium impact issues
    high_impact = [i for i in issues if i.get("severity") == "high"]
    med_impact = [i for i in issues if i.get("severity") == "medium"]
    highlights = (high_impact[:2] + med_impact[:2])[:2]
    
    # Check for A/B testing gap
    has_ab_gap = any(i.get("code") == "missing_ab_testing" for i in issues)
    
    email_lines = []
    email_lines.append(f"Subject: {domain} is leaking ${leak_monthly:,}/mo in revenue (Telemetry Audit)")
    email_lines.append("")
    email_lines.append(f"Hi Team {domain.split('.')[0].capitalize()},")
    email_lines.append("")
    email_lines.append(f"I was running a headless telemetry audit on {domain} and noticed your {platform} store is leaving significant revenue on the table. Our engine calculated an estimated leak of ${leak_monthly:,} per month (${leak_annual:,} annualized) based on Baymard Institute friction models.")
    email_lines.append("")
    
    if highlights:
        for idx, issue in enumerate(highlights, 1):
            desc = issue.get("description", "")
            fix = issue.get("fix", "")
            email_lines.append(f"{idx}. {desc}")
            email_lines.append(f"   -> Fix: {fix}")
            email_lines.append("")
        
    if has_ab_gap:
        stack_str = ", ".join(tech_stack[:3]) if tech_stack else "enterprise tools"
        email_lines.append(f"Additionally, I see you're running {stack_str}, but I couldn't detect an A/B testing platform like Optimizely or VWO. Without A/B testing, CRO decisions are based on opinions rather than statistical evidence.")
        email_lines.append("")
        
    email_lines.append("I've generated a full telemetry report with exact file paths and code snippets to fix these issues.")
    email_lines.append("")
    email_lines.append("Are you open to a quick 10-minute chat next week to discuss how we can plug these leaks?")
    email_lines.append("")
    email_lines.append("Best,")
    email_lines.append("Revenue Operations Engineer")
    
    return "\n".join(email_lines)
