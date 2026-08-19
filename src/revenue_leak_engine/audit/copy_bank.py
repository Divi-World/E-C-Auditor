"""
Decoupled business-facing copy for GEO findings.
Branches based on whether the lead is a confirmed active advertiser.
"""

ISSUE_COPY = {
    "missing_organization_entity": {
        "business_impact_advertiser": "You're actively paying for traffic to this site. But when a customer asks ChatGPT or Google's AI Overview whether you're a real, trustworthy brand, your site can't answer — so that paid traffic's trust doesn't carry into the fastest-growing discovery channel in e-commerce, and a competitor gets recommended instead.",
        "business_impact_generic": "Every visitor who lands on your site is a potential customer. But when they ask ChatGPT or Google's AI Overview whether you're a real, trustworthy brand, your site currently can't answer — so those systems recommend a competitor they can verify instead.",
    },
    "incomplete_product_schema": {
        "business_impact_advertiser": "You're paying for clicks, but an AI shopping agent checking this page can't confirm price or stock. It skips your product and recommends a competitor it can verify — meaning your ad spend is driving traffic to a page that fails to convert in the AI layer.",
        "business_impact_generic": "When an AI shopping agent or search engine checks this page, it can't confirm price or stock with certainty. As a result, it skips your product and recommends a competitor's listing that it can verify — costing you a sale before the customer even reaches checkout.",
    },
    "incomplete_entity_corroboration": {
        "business_impact_advertiser": "Your brand identity is fragmented. AI search engines struggle to confidently identify you over competitors, diluting the ROI of your paid traffic.",
        "business_impact_generic": "Your brand identity is fragmented across your pages. AI search engines struggle to confidently identify and recommend you over competitors with stronger, unified digital footprints.",
    },
    "csr_schema_leak": {
        "business_impact_advertiser": "Lightweight AI shopping agents that do not execute JavaScript see 0% of your catalog data. Your paid traffic is invisible to the fastest-growing segment of automated buyers.",
        "business_impact_generic": "Lightweight AI shopping agents that do not execute JavaScript see 0% of your catalog data. You are invisible to the fastest-growing segment of automated buyers.",
    }
}
