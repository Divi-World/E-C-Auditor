def generate_outreach_email(findings: dict) -> str:
    domain = findings.get("domain", "prospect")
    platform = findings.get("platform", "custom").capitalize()
    leak_monthly = findings.get("estimated_monthly_leak_usd", 0)
    tech_stack = findings.get("tech_stack", [])
    issues = findings.get("issues", [])
    
    high_impact = [i for i in issues if i.get("severity") == "high"]
    med_impact = [i for i in issues if i.get("severity") == "medium"]
    # CITATION-PRIORITY HIGHLIGHTING
    def _priority_score(issue):
        score = 0
        sev = issue.get("severity", "low")
        if sev == "high": score += 10
        elif sev == "medium": score += 5
        else: score += 1
        biz = issue.get("business_impact", "")
        interp = issue.get("interpretation", "")
        if "Baymard" in biz or "Baymard" in interp or bool(interp):
            score += 20  # Citation bonus
        return score

    sorted_issues = sorted(issues, key=_priority_score, reverse=True)
    highlights = sorted_issues[:2]
    
    has_ab_gap = any(i.get("code") == "missing_ab_testing" for i in issues)
    
    if leak_monthly >= 10000:
        subject = f"checkout friction on {domain} (~${leak_monthly:,}/mo leak)"
    elif leak_monthly > 0:
        subject = f"conversion friction on {domain} checkout"
    else:
        subject = f"mobile conversion bottlenecks on {domain}"
        
    lines = []
    lines.append(f"Subject: {subject}")
    lines.append("")
    
    brand = domain.split('.')[0].capitalize()
    lines.append(f"Hi {brand} team,")
    lines.append("")
    
    if leak_monthly > 0:
        lines.append(f"Our automated conversion analysis evaluated {platform} shopping experience today and identified a critical friction point on {domain} that is likely costing you ~${leak_monthly:,}/mo in abandoned carts.")
        lines.append(f"(Estimate based on your traffic tier and severity-weighted findings, benchmarked against Baymard Institute cart-abandonment research.)")
    else:
        lines.append(f"Our automated conversion analysis evaluated {platform} checkout flows today and flagged a few structural bottlenecks on {domain} that are killing mobile conversions.")
    lines.append("")
    
    if highlights:
        lines.append("Specifically, our analysis identified the following revenue leaks:")
        for idx, issue in enumerate(highlights, 1):
            desc = issue.get("description", "").strip()
            
            # Prefer the fields that already carry Baymard/evidence-backed language
            generic_placeholder = "Directly impacts conversion velocity or shopper trust."
            biz_impact = issue.get("business_impact", "")
            interp = issue.get("interpretation", "")
            desc = issue.get("description", "").strip()
            
            if biz_impact and biz_impact != generic_placeholder:
                evidence_text = biz_impact
            elif interp and interp != generic_placeholder:
                evidence_text = interp
            else:
                evidence_text = desc
                
            evidence_text = evidence_text.replace("telemetry", "analysis").replace("headless", "automated")
            if len(evidence_text) > 160:
                evidence_text = evidence_text[:157] + "..."
            lines.append(f"{idx}. {evidence_text}")
        lines.append("")
        
    if has_ab_gap and tech_stack:
        stack_str = ", ".join(tech_stack[:2])
        lines.append(f"I also noticed you are paying for enterprise data tools like {stack_str}, but lack an A/B testing layer (like VWO or Optimizely) to statistically validate your CRO changes.")
        lines.append("")
        
    lines.append("I put together a brief executive teardown showing exactly where the leak is happening, including the exact file paths and code snippets your dev team needs to patch it.")
    lines.append("")
    lines.append("Mind if I send the teardown over?")
    lines.append("")
    lines.append("Best,")
    lines.append("Revenue Operations Engineer")
    
    return "\n".join(lines)
