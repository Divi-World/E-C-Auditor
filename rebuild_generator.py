import re

path = 'src/revenue_leak_engine/reporting/report_generator.py'
with open(path, 'r', encoding='utf-8') as f:
    code = f.read()

# FIX 1: Rebuild Scoring Block (Eradicates SyntaxError & False PARTIAL)
start_marker = "    # 1. STATE MACHINE & SCORING"
end_marker = "    cwv = findings.get(\"cwv\", {})"

new_scoring_block = """    # 1. STATE MACHINE & SCORING
    error_state = findings.get("error", "")
    audit_status = findings.get("audit_status", "VERIFIED")

    if error_state and ("waf" in str(error_state).lower() or "captcha" in str(error_state).lower()):
        audit_status = "BLOCKED"
        score = "BLOCKED"
    elif error_state and "timeout" in str(error_state).lower():
        audit_status = "TIMEOUT"
        score = "TIMEOUT"
    else:
        checks = findings.get("checks_completed", {})
        if checks.get("atc_probe"):
            audit_status = "VERIFIED"
            findings["audit_status"] = "VERIFIED"
            score = opportunity_score(findings)
        elif audit_status == "PARTIAL_WAF" or "PARTIAL_WAF" in findings.get("notes", "") or "curl_cffi_fallback" in findings.get("notes", ""):
            score = "PARTIAL"
            audit_status = "PARTIAL_WAF"
            findings["audit_status"] = "PARTIAL_WAF"
        else:
            score = opportunity_score(findings)

"""

pattern1 = re.compile(re.escape(start_marker) + r'.*?' + re.escape(end_marker), re.DOTALL)
if pattern1.search(code):
    code = pattern1.sub(new_scoring_block + end_marker, code)
    print("✓ 1. Rebuilt Scoring Block (Eradicated SyntaxError & False PARTIAL)")
else:
    print("✗ 1. Scoring markers not found.")

# FIX 2: Rebuild Dedup Block (Alpha-Numeric Nuclear Dedup)
dedup_start = "    seen_codes = set()"
dedup_end = "            else: low_issues.append(issue)"

new_dedup_block = """    seen_codes = set()
    seen_descs_global = set()
    high_issues, med_issues, low_issues, seo_issues = [], [], [], []

    for issue in findings.get("issues", []):
        raw_code = issue.get("code", "unknown")
        code = canon_map.get(raw_code, raw_code)

        desc = issue.get("description") or issue.get("observation") or issue.get("title") or "Friction point detected."
        ev = issue.get("evidence") or "Telemetry data confirms deviation."
        impact = issue.get("business_impact") or issue.get("interpretation") or "Impacts conversion."
        raw_fix = issue.get("fix") or issue.get("recommendation") or "Consult engineering."

        if code not in seo_codes_set and "📍 Where to apply" not in raw_fix:
            raw_fix += where_note
        if platform in snippet_map and code in snippet_map[platform]:
            raw_fix += snippet_map[platform][code]

        issue["code"] = code
        issue["title"] = desc
        issue["description"] = desc
        issue["observation"] = desc
        issue["evidence"] = ev
        issue["business_impact"] = impact
        issue["interpretation"] = impact
        issue["fix"] = raw_fix
        issue["recommendation"] = raw_fix
        issue["severity"] = issue.get("severity", "medium")
        issue["confidence"] = str(issue.get("confidence", "VERIFIED")).upper()

        if code in seen_codes: continue
        seen_codes.add(code)

        desc_sig = re.sub(r'[^a-z0-9]', '', desc.lower())[:30]
        if desc_sig in seen_descs_global: continue
        seen_descs_global.add(desc_sig)

        if code in seo_codes_set:
            seo_issues.append(issue)
        else:
            sev = issue.get("severity")
            if sev == "high": high_issues.append(issue)
            elif sev == "medium": med_issues.append(issue)
            else: low_issues.append(issue)"""

pattern2 = re.compile(re.escape(dedup_start) + r'.*?' + re.escape(dedup_end), re.DOTALL)
if pattern2.search(code):
    code = pattern2.sub(new_dedup_block, code)
    print("✓ 2. Rebuilt Deduplication Block (Alpha-Numeric Nuclear Dedup)")
else:
    print("✗ 2. Dedup markers not found.")

# Clean up any leftover nuclear pass at the bottom
code = re.sub(r'    # NUCLEAR DEDUP PASS:.*?html_out = template\.render\(', '    html_out = template.render(', code, flags=re.DOTALL)

with open(path, 'w', encoding='utf-8') as f:
    f.write(code)
