import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
from revenue_leak_engine.audit.revenue_math import calculate_revenue_risk

def test_enterprise_tier_math():
    findings = {
        "tech_stack": ["Algolia (Search)", "mParticle (CDP)"],
        "platform": "shopify",
        "issues": [
            {"code": "ada_wcag_accessibility_risk"}, # 0.03
            {"code": "slow_ttfb_server_health"},     # 0.03
            {"code": "missing_delivery_urgency"}     # 0.02
        ] # Total = 0.08
    }
    res = calculate_revenue_risk(findings)
    # 500,000 * 0.08 * 85 = 3,400,000
    assert res["estimated_monthly_leak_usd"] == 102000
    assert res["base_sessions"] == 500000

def test_standard_shopify_math():
    findings = {
        "tech_stack": ["Klaviyo (ESP)"],
        "platform": "shopify",
        "issues": [{"code": "no_express_checkout"}] # 0.015
    }
    res = calculate_revenue_risk(findings)
    # 100,000 * 0.015 * 85 = 127,500
    assert res["estimated_monthly_leak_usd"] == 3825
