#!/bin/bash
exec > system_evidence.txt 2>&1

echo "=========================================="
echo "1. FULL SOURCE: site_audit.py"
echo "=========================================="
cat -n src/revenue_leak_engine/audit/site_audit.py

echo "=========================================="
echo "2. FULL SOURCE: report_generator.py"
echo "=========================================="
cat -n src/revenue_leak_engine/reporting/report_generator.py

echo "=========================================="
echo "3. FULL SOURCE: revenue_math.py"
echo "=========================================="
cat -n src/revenue_leak_engine/audit/revenue_math.py

echo "=========================================="
echo "4. FULL PIPELINE SOURCE"
echo "=========================================="
cat -n src/revenue_leak_engine/pipeline.py

echo "=========================================="
echo "5. FULL TEST SUITE + RESULTS"
echo "=========================================="
pytest

echo "=========================================="
echo "6. RAW REPRODUCIBILITY DATA - 10 RUNS, ALL FIELDS, NO CHERRY-PICKING"
echo "=========================================="
for i in {1..10}; do
    echo "--- RUN $i ---"
    python -c "from revenue_leak_engine.audit.site_audit import audit_site; import json; print(json.dumps(audit_site('gymshark.com'), indent=2))"
done

echo "=========================================="
echo "7. DEAD CODE CHECK"
echo "=========================================="
grep -c -E "def _audit_checkout_telemetry|def _sample_product_integrity|def _check_variant_integrity|def _audit_homepage_and_awareness|def _audit_homepage_and_collection" src/revenue_leak_engine/audit/site_audit.py

echo "=========================================="
echo "8. MODULE ISOLATION"
echo "=========================================="
grep -rn "geo_audit" src/revenue_leak_engine/audit/site_audit.py
grep -rn "site_audit" src/revenue_leak_engine/audit/geo_audit.py

echo "=========================================="
echo "9. GIT STATE"
echo "=========================================="
git log --oneline -n 15
echo "---"
git status
echo "---"
git diff --stat HEAD~5

echo "=========================================="
echo "10. ALL TEST FILES THAT EXIST"
echo "=========================================="
for f in tests/*.py; do
    echo "--- $f ---"
    cat "$f"
done
