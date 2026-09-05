#!/bin/bash
echo "=========================================="
echo "1. FULL SOURCE: site_audit.py"
echo "=========================================="
cat -n src/revenue_leak_engine/audit/site_audit.py

echo ""
echo "=========================================="
echo "2. FULL SOURCE: report_generator.py"
echo "=========================================="
cat -n src/revenue_leak_engine/reporting/report_generator.py

echo ""
echo "=========================================="
echo "3. FULL SOURCE: revenue_math.py"
echo "=========================================="
find . -iname "revenue_math.py" -exec cat -n {} \;

echo ""
echo "=========================================="
echo "4. FULL PIPELINE SOURCE"
echo "=========================================="
cat -n src/revenue_leak_engine/pipeline.py

echo ""
echo "=========================================="
echo "5. FULL TEST SUITE + RESULTS"
echo "=========================================="
export PYTHONPATH=src
python -m pytest tests/ -v 2>&1

echo ""
echo "=========================================="
echo "6. RAW REPRODUCIBILITY DATA - 10 RUNS, ALL FIELDS, NO CHERRY-PICKING"
echo "=========================================="
python -c "
import json
from revenue_leak_engine.audit.site_audit import audit_site
for i in range(10):
    try:
        r = audit_site('gymshark.com')
        print(f'--- RUN {i+1} ---')
        print(json.dumps({k: v for k, v in r.items() if k != 'screenshot_b64'}, indent=2, default=str))
    except Exception as e:
        print(f'--- RUN {i+1} CRASHED: {type(e).__name__}: {e} ---')
"

echo ""
echo "=========================================="
echo "7. DEAD CODE CHECK"
echo "=========================================="
for fn in _audit_checkout_telemetry _sample_product_integrity _check_variant_integrity _audit_homepage_and_awareness _audit_homepage_and_collection; do
    count=$(grep -c "$fn(" src/revenue_leak_engine/audit/site_audit.py)
    echo "$fn: $count occurrence(s)"
done

echo ""
echo "=========================================="
echo "8. MODULE ISOLATION"
echo "=========================================="
grep -n "geo_audit\|geo_report_generator" src/revenue_leak_engine/audit/site_audit.py src/revenue_leak_engine/reporting/report_generator.py 2>/dev/null
grep -n "site_audit\|report_generator" src/revenue_leak_engine/audit/geo_audit.py 2>/dev/null
echo "(no output above two greps = isolation intact)"

echo ""
echo "=========================================="
echo "9. GIT STATE"
echo "=========================================="
git log --oneline -20
echo "---"
git status --short
echo "---"
git diff --stat HEAD~15 HEAD 2>/dev/null

echo ""
echo "=========================================="
echo "10. ALL TEST FILES THAT EXIST"
echo "=========================================="
find tests/ -name "*.py" -exec echo "--- {} ---" \; -exec cat {} \;

echo ""
echo "DUMP COMPLETE"
