import re

path = 'src/revenue_leak_engine/audit/site_audit.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

changes = 0

# FIX 1: Remove duplicate _check_ttfb call
old_ttfb = """cwv = _extract_cwv_and_friction(page)
_check_ttfb(page, findings)
findings["checks_completed"]["cwv"] = True"""
new_ttfb = """cwv = _extract_cwv_and_friction(page)
findings["checks_completed"]["cwv"] = True"""
if old_ttfb in content:
    content = content.replace(old_ttfb, new_ttfb)
    changes += 1
    print("[OK] 1. Duplicate TTFB call removed")

# FIX 2: Ensure deduped_issues is assigned back to findings["issues"]
pattern_dedup = r"(        deduped_issues\.append\(issue\)\n)(    # BULLETPROOF NUCLEAR DEDUP)"
replacement_dedup = r"\1    findings[\"issues\"] = deduped_issues\n\n\2"
if re.search(pattern_dedup, content):
    content = re.sub(pattern_dedup, replacement_dedup, content, count=1)
    changes += 1
    print("[OK] 2. Deduplication assignment fixed (findings['issues'] = deduped_issues)")

# FIX 3: Fix cart probe indentation and wire _audit_checkout_telemetry
old_cart = """                try:
                    _check_checkout_behavior(page, domain, findings)
                    findings["checks_completed"]["checkout_behavior"] = True
                except Exception as _e:
                    findings["notes"] += f"checkout_behavior_failed: {_e}. "
                if not cart_express: findings["issues"].append({"code": "cart_no_express_checkout""""

new_cart = """                try:
                    _check_checkout_behavior(page, domain, findings)
                    findings["checks_completed"]["checkout_behavior"] = True
                except Exception as _e:
                    findings["notes"] += f"checkout_behavior_failed: {_e}. "
                
                try:
                    _audit_checkout_telemetry(page, findings, domain)
                except Exception as _e:
                    findings["notes"] += f"checkout_telemetry_failed: {_e}. "

                if not cart_express:
                    findings["issues"].append({"code": "cart_no_express_checkout"""

if old_cart in content:
    content = content.replace(old_cart, new_cart)
    changes += 1
    print("[OK] 3. Cart probe indentation fixed & telemetry wired")

if changes > 0:
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"\n[SUCCESS] {changes} Structural Fixes Applied.")
else:
    print("\n[INFO] No changes applied.")
