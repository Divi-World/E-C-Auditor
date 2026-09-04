"""
Single Source of Truth for Revenue Leak Estimation.
Defensible via Baymard Institute cart abandonment statistics.
"""
def calculate_revenue_risk(findings: dict) -> dict:
    t = findings.get("tech_stack", [])
    if any(x in t for x in ["Segment (CDP)", "mParticle (CDP)", "Algolia (Search)"]):
        base_monthly_sessions = 500000
    elif "shopify" in findings.get("platform", "").lower():
        base_monthly_sessions = 100000
    else:
        base_monthly_sessions = 30000
        
    avg_order_value = 85  
    
    # Baymard Institute Impact Weights
    penalties = {
        "forced_account_creation": 0.05,      # Baymard: 24% abandon forced login
        "hidden_shipping_costs": 0.04,        # Baymard: 68% abandon surprise costs
        "checkout_hidden_fees_detected": 0.04,
        "ada_wcag_accessibility_risk": 0.03,  # Legal risk + 15% disabled pop.
        "slow_ttfb_server_health": 0.03,
        "no_add_to_cart_found": 0.03,
        "missing_delivery_urgency": 0.02,
        "heavy_client_side_js": 0.02,
        "no_express_checkout": 0.015,
        "cart_no_express_checkout": 0.015,
        "add_to_cart_below_fold": 0.01,
        "missing_sticky_atc": 0.01,
        "cart_no_shipping_estimator": 0.02
    }
    
    raw_penalty = sum(penalties.get(i.get("code"), 0) for i in findings.get("issues", []))
    total_penalty = min(raw_penalty, 0.25)
    penalty_capped = raw_penalty > 0.25
    monthly_leak = int(base_monthly_sessions * 0.03 * total_penalty * avg_order_value)  # 3% E-commerce Conversion Rate
    
    return {
        "estimated_monthly_leak_usd": monthly_leak,
        "estimated_annual_leak_usd": monthly_leak * 12,
        "base_sessions": base_monthly_sessions,
        "total_penalty_pct": total_penalty,
        "penalty_capped": penalty_capped
    }
