#!/bin/bash
echo "=================================================="
echo "SECTION 1: STATIC CODE HEALTH"
echo "=================================================="
echo "--- Dead/unwired functions (defined but never called) ---"
for fn in _audit_checkout_telemetry _sample_product_integrity _check_variant_integrity _audit_homepage_and_awareness; do
    count=$(grep -c "$fn(" src/revenue_leak_engine/audit/site_audit.py 2>/dev/null)
    echo "$fn: $count occurrence(s) (1 = definition only, dead code | 2+ = wired)"
done

echo ""
echo "--- Duplicate function definitions (same name defined twice = bug risk) ---"
grep -oP '^def \K\w+' src/revenue_leak_engine/audit/site_audit.py | sort | uniq -c | sort -rn | awk '$1 > 1'

echo ""
echo "--- Bare/broad except blocks (silent failure risk) ---"
grep -c "except Exception: pass\|except: pass" src/revenue_leak_engine/audit/site_audit.py

echo ""
echo "--- Unresolved markers ---"
grep -n "TODO\|FIXME\|XXX\|HACK" src/revenue_leak_engine/audit/site_audit.py src/revenue_leak_engine/reporting/report_generator.py src/revenue_leak_engine/audit/geo_audit.py 2>/dev/null

echo ""
echo "--- Syntax check on all core files ---"
for f in src/revenue_leak_engine/audit/site_audit.py src/revenue_leak_engine/audit/geo_audit.py src/revenue_leak_engine/reporting/report_generator.py src/revenue_leak_engine/pipeline.py; do
    python -m py_compile "$f" 2>&1 && echo "$f: CLEAN" || echo "$f: SYNTAX ERROR"
done

echo ""
echo "=================================================="
echo "SECTION 2: MODULE ISOLATION (CRO/GEO wall)"
echo "=================================================="
grep -n "geo_audit\|geo_report_generator" src/revenue_leak_engine/audit/site_audit.py src/revenue_leak_engine/reporting/report_generator.py 2>/dev/null
grep -n "site_audit\|report_generator" src/revenue_leak_engine/audit/geo_audit.py 2>/dev/null
echo "(no output above = isolation intact)"

echo ""
echo "=================================================="
echo "SECTION 3: SCORING SOURCE OF TRUTH"
echo "=================================================="
echo "--- CRO opportunity_score locations (should be exactly ONE real implementation) ---"
grep -n "^def opportunity_score" src/revenue_leak_engine/reporting/report_generator.py
grep -n "findings\[.opportunity_score.\] =" src/revenue_leak_engine/audit/site_audit.py
echo "(second grep should return NOTHING - a match means a dead duplicate scorer still exists)"

echo ""
echo "--- GEO weights (for manual math verification) ---"
grep -n "^WEIGHTS" -A6 src/revenue_leak_engine/audit/geo_audit.py

echo ""
echo "=================================================="
echo "SECTION 4: REVENUE-LEAK MODEL INPUTS"
echo "=================================================="
grep -n "traffic\|AOV\|aov" src/revenue_leak_engine/audit/revenue_math.py 2>/dev/null | head -20
echo "(check: are these real inputs or hardcoded guesses?)"

echo ""
echo "=================================================="
echo "SECTION 5: TEST SUITE"
echo "=================================================="
export PYTHONPATH=src
python -m pytest tests/ --tb=short -q 2>&1

echo ""
echo "=================================================="
echo "SECTION 6: REPRODUCIBILITY (honest version - tracks inconclusive, not just hash)"
echo "=================================================="
python -c "
from revenue_leak_engine.audit.site_audit import audit_site
for i in range(5):
    r = audit_site('gymshark.com')
    inconclusive = 'inconclusive' in r.get('notes', '').lower()
    print(f'Run {i+1}: hash={r.get(\"findings_hash\")}, score={r.get(\"opportunity_score\", \"N/A (check report_generator)\")}, issue_count={len(r.get(\"issues\", []))}, inconclusive_flagged={inconclusive}')
"

echo ""
echo "=================================================="
echo "SECTION 7: CROSS-REPORT LABEL CONTRADICTIONS"
echo "=================================================="
for f in data/reports/*.html; do
    if grep -q "Commercial Opportunity" "$f" 2>/dev/null; then
        score=$(grep -oP '(?<=Score: )[\d.]+' "$f" | head -1)
        label=$(grep -oP '(?<=Commercial Opportunity: )\w+' "$f" | head -1)
        echo "$(basename $f): score=$score label=$label"
    fi
done

echo ""
echo "=================================================="
echo "SECTION 8: GIT STATE"
echo "=================================================="
git log --oneline -10
echo "---"
git status --short

echo ""
echo "=================================================="
echo "SECTION 9: PLATFORM DETECTION ACCURACY SPOT-CHECK"
echo "=================================================="
python -c "
from revenue_leak_engine.audit.geo_audit import audit_geo
known = {'gymshark.com': 'shopify', 'universalyums.com': 'woocommerce', 'id.coach.com': 'magento'}
for domain, expected in known.items():
    r = audit_geo(domain)
    actual = r.get('platform_detected', 'MISSING')
    match = 'OK' if actual == expected else 'MISMATCH'
    print(f'{domain}: expected={expected} actual={actual} [{match}]')
"

echo ""
echo "AUDIT COMPLETE"
