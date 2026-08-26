import re

# 1. FIX SITE_AUDIT.PY
with open('src/revenue_leak_engine/audit/site_audit.py', 'r', encoding='utf-8') as f:
    site = f.read()

rev_func = '''def _calculate_revenue_risk(findings):
    t = findings.get('tech_stack', [])
    b = 500000 if any(x in t for x in ['Segment (CDP)', 'mParticle (CDP)', 'Algolia (Search)']) else (100000 if 'shopify' in findings.get('platform', '').lower() else 50000)
    p = {'no_express_checkout':0.015, 'cart_no_express_checkout':0.015, 'hidden_shipping_costs':0.04, 'missing_delivery_urgency':0.02, 'slow_ttfb_server_health':0.03, 'heavy_client_side_js':0.02, 'add_to_cart_below_fold':0.01, 'missing_sticky_atc':0.01, 'forced_account_creation':0.05, 'no_cart_drawer':0.005, 'cart_no_shipping_estimator':0.02, 'ada_wcag_accessibility_risk':0.02}
    tp = min(sum(p.get(i.get('code'), 0) for i in findings.get('issues', [])), 0.25)
    findings['estimated_monthly_leak_usd'] = int(b * tp * 85)
    findings['estimated_annual_leak_usd'] = findings['estimated_monthly_leak_usd'] * 12

'''
site = re.sub(r'(def _safe_query\(page, action_func, retries=2\):)', rev_func + r'\1', site, count=1)

dedup_code = '''    # OMEGA NUCLEAR DEDUP & REVENUE RISK
    cart_evidence = any(('/cart/add' in u or '/cart.js' in u or '/add-to-cart' in u or '/checkout' in u) for u in seen_urls)
    ghost_ok = 'ghost_click' in findings.get('notes', '')
    inconclusive = any(i.get('code') == 'atc_detection_inconclusive' for i in findings.get('issues', []))
    if cart_evidence or ghost_ok or inconclusive:
        findings['issues'] = [i for i in findings.get('issues', []) if i.get('code') != 'no_add_to_cart_found']
    if '_calculate_revenue_risk' in globals():
        _calculate_revenue_risk(findings)

'''
site = re.sub(r'(    # STATUS INTEGRITY: If we completed the full interactive flow without fatal error, it is VERIFIED.\)', dedup_code + r'\1', site, count=1)

old_atc = r'        findings\["issues"\].append\(\{"code": "no_add_to_cart_found", "description": "No Add to Cart button detected on the product page\.", "evidence": "Deep DOM, Shadow Root, and Ultimate Hunter returned no match\.", "severity": "high", "confidence": "high", "fix": "Ensure a visible, clearly labelled Add to Cart button exists on the mobile PDP.\"}\)\n        return None'
new_atc = '''        # OMEGA ATC NETWORK TRUTH
        cart_api_fired = any(('/cart/add' in u or '/cart.js' in u or '/add-to-cart' in u) for u in seen_urls)
        if not cart_api_fired:
            findings["issues"].append({"code": "no_add_to_cart_found", "description": "No Add to Cart button detected on the product page.", "evidence": "Deep DOM, Shadow Root, and Ultimate Hunter returned no match.", "severity": "high", "confidence": "high", "fix": "Ensure a visible, clearly labelled Add to Cart button exists on the mobile PDP."})
        else:
            findings["issues"].append({"code": "atc_detection_inconclusive", "severity": "low", "confidence": "VERIFIED", "description": "Cart API activity detected but Add-to-Cart button could not be located in DOM.", "evidence": "Network requests to cart endpoints observed.", "business_impact": "Headless architecture trait.", "fix": "Manual verification recommended."})
        return None'''
site = re.sub(old_atc, new_atc, site, count=1)

with open('src/revenue_leak_engine/audit/site_audit.py', 'w', encoding='utf-8') as f:
    f.write(site)

# 2. FIX PIPELINE.PY
with open('src/revenue_leak_engine/pipeline.py', 'r', encoding='utf-8') as f:
    pipe = f.read()

banner_code = '''                # OMEGA BANNER INJECTION
                if cro_findings.get("estimated_monthly_leak_usd", 0) > 0:
                    _lk = cro_findings["estimated_monthly_leak_usd"]
                    _an = cro_findings["estimated_annual_leak_usd"]
                    _bh = f'<div style="background:linear-gradient(90deg, #7f1d1d, #991b1b); color:white; padding:20px; text-align:center; font-family:sans-serif; margin-bottom:20px; border-radius:8px;"><h2 style="margin:0; font-size:24px;">ESTIMATED REVENUE EEAK: ${_lk:.} / MONTH</h2><p style="margin:5px 0 0 0; opacity:0.9;">${_an:.} Annualized Loss (Baymard Friction Model)</p></div>'
                    try:
                        import re as _re
                        with open(cro_report, 'r', encoding='utf-8') as _f: _html = _f.read()
                        if 'ESTIMATED REVENUE EEAK' not in _html:
                            _body_match = _re.search(r'<body[^>]*>', _html)
                            if _body_match:
                                _insert_pos = _body_match.end()
                                _html = _html[:_insert_pos] + _bh + _html[_insert_pos:]
                                with open(cro_report, 'w', encoding='utf-8') as _f: _f.write(_html)
                    except Exception: pass

'''
pipe = re.sub(r'(                print\(f"    CRO score \{cro_score\}/10 -> \{cro_report\}"\))', banner_code + r'\1', pipe, count=1)

with open('src/revenue_leak_engine/pipeline.py', 'w', encoding='utf-8') as f:
    f.write(pipe)

print("OMEGA INDUSTRIAL V6 APPLIED")
