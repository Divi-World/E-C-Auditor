"""
Decoupled business-facing copy for GEO findings.
Separates technical detection from sales-literate, ad-spend-aware positioning.
"""

ISSUE_COPY = {
    "missing_organization_entity": {
        "business_impact": "Every visitor who lands on your site is a potential customer. But when they ask ChatGPT or Google's AI Overview whether you're a real, trustworthy brand, your site currently can't answer — so those systems recommend a competitor they can verify instead.",
        "fix_intro": "Add Organization schema so AI systems can confirm who you are before recommending you.",
    },
    "incomplete_product_schema": {
        "business_impact": "When an AI shopping agent or search engine checks this page, it can't confirm price or stock with certainty. As a result, it skips your product and recommends a competitor's listing that it can verify — costing you a sale before the customer even reaches checkout.",
        "fix_intro": "Complete your Product schema so AI shopping agents can actually verify and recommend you.",
    },
    "incomplete_entity_corroboration": {
        "business_impact": "Your brand identity is fragmented across your pages. AI search engines struggle to confidently identify and recommend you over competitors with stronger, unified digital footprints.",
        "fix_intro": "Deploy global Organization schema to solidify your brand's Knowledge Graph presence.",
    },
    "csr_schema_leak": {
        "business_impact": "Lightweight AI shopping agents that do not execute JavaScript see 0% of your catalog data. You are invisible to the fastest-growing segment of automated buyers.",
        "fix_intro": "Implement Server-Side Rendering (SSR) or inject JSON-LD directly into the raw HTML.",
    }
}
