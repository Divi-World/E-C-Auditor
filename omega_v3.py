import re

# 1. Fix site_audit.py
s = 'src/revenue_leak_engine/audit/site_audit.py'
with open(s, 'r', encoding='utf-8') as f:
    c = f.read()

# Ensure _calculate_revenue_risk exists
if 'def _calculate_revenue_risk' not in c:
    func = '''
def _calculate_revenue_risk(findings):
    t = findings.get("tech_stack", [])
    b = 500000 if any(x in t for x in ["Segment (CDP)", "mParticle (CDP)", "Algolia (Search)"]) else (100000 if "shopify" in findings.get("platform", "").lower() else 50000)
    p = {"no_express_checkout":0.015, "cart_no_express_checkout":0.015, "hidden_shipping_costs":0.04, "missing_delivery_urgency":0.02, "slow_ttfb_server_health":0.03, "heavy_client_side_js":0.02, "add_to_cart_below_fold":0.01, "missing_sticky_atc":0.01, "forced_account_creation":0.05, "no_cart_drawer":0.005, "cart_no_shipping_estimator":0.02, "ada_wcag_accessibility_risk":0.02}
    tp = min(sum(p.get(i.get("code"), 0) for i in findings.get("issues", [])), 0.25)
    findings["estimated_monthly_leak_usd"] = int(b * tp * 85)
    findings["estimated_annual_leak_usd"] = findings["estimated_monthly_leak_usd"] * 12
'''
    c = c.replace('def _safe_query', func + '\ndef _safe_query')

# Inject call at the end of audit_site using the bulletproof line-search method
if '_calculate_revenue_risk(findings)' not in c:
    lines = c.split('\n')
    for i in range(len(lines)-1, -1, -1):
        if lines[i] == '    return findings':
            inject = '''
    # NUCLEAR DEDUP: Remove false positive if cart evidence exists
    cart_evidence = any(('/cart/add' in u or '/cart.js' in u or '/add-to-cart' in u or '/checkout' in u) for u in seen_urls)
    ghost_ok = "ghost_click" in findings.get("notes", "")
    inconclusive = any(i.get("code") == "atc_detection_inconclusive" for i in findings.get("issues", []))
    if cart_evidence or ghost_ok or inconclusive:
        findings["issues"] = [i for i in findings.get("issues", []) if i.get("code") != "no_add_to_cart_found"]

    # OMEGA REVENUE RISK
    _calculate_revenue_risk(findings)
'''
            lines.insert(i, inject)
            c = '\n'.join(lines)
            break

# Fix TTFB healthy state
old_ttfb = '''        if ttfb is not None:
            findings["ttfb_ms"] = ttfb
            if ttfb > 800:
                findings["issues"].append({
                    "code": "slow_ttfb_server_health", "severity": "high", "confidence": "VERIFIED",
                    "description": f"Server Response Time (TTFB) is dangerously slow ({ttfb}ms).",
                    "evidence": f"Time to First Byte is {ttfb}ms (Target: <800ms). Measured via Navigation Timing API.",
                    "business_impact": "TTFB measures raw hosting/server health. A slow TTFB means the server is struggling, bottlenecking all subsequent frontend optimizations.",
                    "fix": "Upgrade hosting infrastructure, implement server-side caching (Redis/Varnish), or use a premium CDN (Cloudflare/Fastly)."
                })
        else:
            findings["ttfb_ms"] = None'''

new_ttfb = '''        if ttfb is not None:
            findings["ttfb_ms"] = ttfb
            if ttfb > 800:
                findings["issues"].append({
                    "code": "slow_ttfb_server_health", "severity": "high", "confidence": "VERIFIED",
                    "description": f"Server Response Time (TTFB) is dangerously slow ({ttfb}ms).",
                    "evidence": f"Time to First Byte is {ttfb}ms (Target: <800ms). Measured via Navigation Timing API.",
                    "business_impact": "TTFB measures raw hosting/server health. A slow TTFB means the server is struggling, bottlenecking all subsequent frontend optimizations.",
                    "fix": "Upgrade hosting infrastructure, implement server-side caching (Redis/Varnish), or use a premium CDN (Cloudflare/Fastly)."
                })
            else:
                findings["ttfb_status"] = f"Server responded in {ttfb}ms — within healthy range (<800ms)."
        else:
            findings["ttfb_ms"] = None'''

if old_ttfb in c and 'ttfb_status' not in c:
    c = c.replace(old_ttfb, new_ttfb)

with open(s, 'w', encoding='utf-8') as f:
    f.write(c)

# 2. Fix pipeline.py
p = 'src/revenue_leak_engine/pipeline.py'
with open(p, 'r', encoding='utf-8') as f:
    pc = f.read()

# Bulletproof banner injection
target = 'print(f"    CRO score {cro_score}/10 -> {cro_report}")'
if 'ESTIMATED REVENUE LEAK' not in pc and target in pc:
    banner = '''
        # OMEGA BANNER INJECTION
        if cro_findings.get("estimated_monthly_leak_usd", 0) > 0:
            _lk = cro_findings["estimated_monthly_leak_usd"]
            _an = cro_findings["estimated_annual_leak_usd"]
            _bh = f'<div style="background:linear-gradient(90deg, #7f1d1d, #991b1b); color:white; padding:20px; text-align:center; font-family:sans-serif; margin-bottom:20px; border-radius:8px;"><h2 style="margin:0; font-size:24px;">ESTIMATED REVENUE LEAK: ${_lk:,} / MONTH</h2><p style="margin:5px 0 0 0; opacity:0.9;">${_an:,} Annualized Loss (Baymard Friction Model)</p></div>'
            try:
                import re
                with open(cro_report, 'r', encoding='utf-8') as f: html = f.read()
                if 'ESTIMATED REVENUE LEAK' not in html:
                    body_match = re.search(r'<body[^>]*>', html)
                    if body_match:
                        insert_pos = body_match.end()
                        html = html[:insert_pos] + _bh + html[insert_pos:]
                        with open(cro_report, 'w', encoding='utf-8') as f: f.write(html)
            except Exception: pass

'''
    pc = pc.replace(target, banner + target)
    with open(p, 'w', encoding='utf-8') as f:
        f.write(pc)

print("OMEGA INDUSTRIAL V3 APPLIED")
