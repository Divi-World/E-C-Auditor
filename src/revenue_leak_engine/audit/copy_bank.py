"""
Decoupled business-facing copy for GEO findings.
Strictly defensible, evidence-based language.
"""

ISSUE_COPY = {
    "missing_organization_entity": {
        "business_impact_advertiser": "Missing explicit Organization/Brand structured data can reduce machine-readable entity clarity for systems that rely on structured signals when identifying and corroborating a brand, potentially diluting the ROI of your paid traffic.",
        "business_impact_generic": "Missing explicit Organization/Brand structured data can reduce machine-readable entity clarity for systems that rely on structured signals when identifying and corroborating a brand.",
    },
    "incomplete_product_schema": {
        "business_impact_advertiser": "Incomplete machine-readable product data may reduce eligibility and reliability for search, shopping surfaces, and emerging AI-assisted discovery systems, meaning your ad spend drives traffic to pages that automated systems cannot fully verify.",
        "business_impact_generic": "Incomplete machine-readable product data may reduce eligibility and reliability for search, shopping surfaces, and emerging AI-assisted discovery systems.",
    },
    "incomplete_entity_corroboration": {
        "business_impact_advertiser": "Your brand identity is fragmented across sampled pages. AI search engines struggle to confidently identify you over competitors, which can dilute the ROI of your paid traffic.",
        "business_impact_generic": "Your brand identity is fragmented across sampled pages. AI search engines struggle to confidently identify and recommend you over competitors with stronger, unified digital footprints.",
    },
    "csr_schema_leak": {
        "business_impact_advertiser": "Lightweight AI shopping agents that do not execute JavaScript see 0% of your catalog data. Your paid traffic is invisible to the fastest-growing segment of automated buyers.",
        "business_impact_generic": "Lightweight AI shopping agents that do not execute JavaScript see 0% of your catalog data. You are invisible to the fastest-growing segment of automated buyers.",
    }
}
