from revenue_leak_engine.audit.geo_audit import audit_geo

DOMAINS = ["gymshark.com", "ritual.com", "beautyitis.com", "universalyums.com", "id.coach.com"]

IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.gif', '.webp')

for domain in DOMAINS:
    r = audit_geo(domain)
    problems = []

    # Check 1: no image URLs sampled as product/entity pages
    for issue in r.get("issues", []):
        for url in issue.get("affected_urls", []):
            if any(url.lower().split('?')[0].endswith(ext) for ext in IMAGE_EXTENSIONS):
                problems.append(f"image URL in affected_urls: {url}")

    # Check 2: capabilities PASS shouldn't coexist with a failure issue for same protocol
    caps = r.get("agentic_capabilities", {})
    for issue in r.get("issues", []):
        if issue["code"] in ("mcp_handshake_failed", "ucp_handshake_failed"):
            if caps.get("MCP") == "PASS" or caps.get("UCP") == "PASS":
                problems.append(f"contradiction: {issue['code']} present but capability shows PASS")

    # Check 3: unmeasured dimension should be null, not a number
    for dim, measured in r.get("dimensions_measured", {}).items():
        if not measured and r["dimensions"].get(dim) not in (None,):
            problems.append(f"{dim} marked unmeasured but has a numeric value: {r['dimensions'][dim]}")

    # Check 4: platform_detected always present
    if "platform_detected" not in r:
        problems.append("platform_detected missing entirely")

    status = "OK" if not problems else "ISSUES: " + "; ".join(problems)
    print(f"{domain:20} {status}")
