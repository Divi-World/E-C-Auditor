import os

geo_path = 'src/revenue_leak_engine/audit/geo_audit.py'
with open(geo_path, 'r', encoding='utf-8') as f:
    geo = f.read()

# 1. Safe string replacements for fabricated snippet data (NO REGEX)
# This directly targets the exact fabricated strings your partner found.
geo = geo.replace('"Premium product offering."', '"REPLACE_WITH_PRODUCT_DESCRIPTION"')
geo = geo.replace('"0.00"', '"REPLACE_WITH_PRICE"')
geo = geo.replace('"N/A"', '"REPLACE_WITH_SKU"')
print("1. Snippet fabrication strings replaced safely (Zero regex used).")

# 2. Reconcile Answerability Dimension safely
ans_logic = """
    # Partner Directive: Reconcile Answerability Dimension
    try:
        ans_matrix = findings.get("answerability_matrix", {})
        verified = sum(1 for k, v in ans_matrix.items() if v in [True, "PASS", 200] and k in ["privacy", "terms", "shipping", "returns"])
        if verified == 0:
            findings["dimensions"]["answerability"] = min(findings["dimensions"].get("answerability", 10.0), 4.0)
        elif verified <= 2:
            findings["dimensions"]["answerability"] = min(findings["dimensions"].get("answerability", 10.0), 7.0)
    except Exception:
        pass
"""
if "Reconcile Answerability Dimension" not in geo:
    idx = geo.rfind("    return findings")
    if idx != -1:
        geo = geo[:idx] + ans_logic + geo[idx:]
        print("2. Answerability reconciliation injected safely.")

with open(geo_path, 'w', encoding='utf-8') as f:
    f.write(geo)
