def generate_outreach_email(findings: dict) -> str:
    domain = findings.get("domain", "prospect")
    platform = findings.get("platform", "custom").capitalize()
    leak_monthly = findings.get("estimated_monthly_leak_usd", 0)
    tech_stack = findings.get("tech_stack", [])
    issues = findings.get("issues", [])
    
    high_impact = [i for i in issues if i.get("severity") == "high"]
    med_impact = [i for i in issues if i.get("severity") == "medium"]
    highlights = (high_impact[:2] + med_impact[:2])[:2]
    
    has_ab_gap = any(i.get("code") == "missing_ab_testing" for i in issues)
    
    if leak_monthly >= 10000:
        subject = f"checkout friction on {domain} (~${leak_monthly:,}/mo leak)"
    elif leak_monthly > 0:
        subject = f"telemetry data on {domain} checkout"
    else:
        subject = f"mobile conversion bottlenecks on {domain}"
        
    lines = []
    lines.append(f"Subject: {subject}")
    lines.append("")
    
    brand = domain.split('.')[0].capitalize()
    lines.append(f"Hi {brand} team,")
    lines.append("")
    
    if leak_monthly > 0:
        lines.append(f"Our telemetry engine was crawling {platform} checkout flows today and flagged a structural friction point on {domain} that is likely costing you ~${leak_monthly:,}/mo in abandoned carts.")
    else:
        lines.append(f"Our telemetry engine was crawling {platform} checkout flows today and flagged a few structural bottlenecks on {domain} that are killing mobile conversions.")
    lines.append("")
    
    if highlights:
        lines.append("Specifically, our headless browser verified:")
        for idx, issue in enumerate(highlights, 1):
            desc = issue.get("description", "").strip()
            if len(desc) > 140:
                desc = desc[:137] + "..."
            lines.append(f"{idx}. {desc}")
        lines.append("")
        
    if has_ab_gap and tech_stack:
        stack_str = ", ".join(tech_stack[:2])
        lines.append(f"I also noticed you are paying for enterprise data tools like {stack_str}, but lack an A/B testing layer (like VWO or Optimizely) to statistically validate your CRO changes.")
        lines.append("")
        
    lines.append("I put together a 2-minute technical teardown showing exactly where the leak is happening, including the exact file paths and code snippets your dev team needs to patch it.")
    lines.append("")
    lines.append("Mind if I send the teardown over?")
    lines.append("")
    lines.append("Best,")
    lines.append("Revenue Operations Engineer")
    
    return "\n".join(lines)
