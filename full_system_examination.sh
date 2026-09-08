#!/bin/bash
echo "################################################"
echo "PART 1: COMPLETE SOURCE FILES"
echo "################################################"
for f in src/revenue_leak_engine/audit/site_audit.py \
         src/revenue_leak_engine/reporting/report_generator.py \
         src/revenue_leak_engine/reporting/templates/report.html \
         src/revenue_leak_engine/audit/geo_audit.py \
         src/revenue_leak_engine/pipeline.py \
         src/revenue_leak_engine/audit/revenue_math.py; do
    if [ -f "$f" ]; then
        echo "=== FILE: $f ($(wc -l < "$f") lines) ==="
        cat -n "$f"
    else
        echo "=== FILE NOT FOUND: $f ==="
        find . -iname "$(basename $f)" 2>/dev/null
    fi
    echo ""
done

echo "################################################"
echo "PART 2: EVERY FUNCTION DEFINITION AND WHERE IT'S CALLED"
echo "################################################"
grep -n "^def \|^    def " src/revenue_leak_engine/audit/site_audit.py | while read -r line; do
    fname=$(echo "$line" | grep -oP '(?<=def )\w+')
    linenum=$(echo "$line" | cut -d: -f1)
    callcount=$(grep -c "$fname(" src/revenue_leak_engine/audit/site_audit.py)
    echo "Line $linenum: $fname -> called $callcount time(s) in file"
done

echo ""
echo "################################################"
echo "PART 3: EVERY RETURN STATEMENT AND ITS LINE NUMBER (audit_site early-exit map)"
echo "################################################"
grep -n "return findings\|return None\|return {" src/revenue_leak_engine/audit/site_audit.py

echo ""
echo "################################################"
echo "PART 4: RESOLVE THE cwv=None CONTRADICTION DIRECTLY"
echo "################################################"
export PYTHONPATH=src
python -c "
from revenue_leak_engine.audit.site_audit import audit_site
r = audit_site('gymshark.com')
print('cwv key present:', 'cwv' in r)
print('cwv value:', repr(r.get('cwv')))
print('cwv type:', type(r.get('cwv')))
try:
    from revenue_leak_engine.reporting.report_generator import generate_report
    path = generate_report(r)
    print('generate_report succeeded:', path)
except Exception as e:
    import traceback
    print('generate_report FAILED:')
    traceback.print_exc()
"

echo ""
echo "################################################"
echo "PART 5: FULL TEST SUITE, VERBOSE"
echo "################################################"
python -m pytest tests/ -v 2>&1

echo ""
echo "################################################"
echo "PART 6: 10-RUN RAW FULL JSON DUMP (safe .get() based, no crash risk)"
echo "################################################"
python -c "
import json
from revenue_leak_engine.audit.site_audit import audit_site
for i in range(10):
    try:
        r = audit_site('gymshark.com')
        print(f'--- RUN {i+1} ---')
        print(json.dumps({k: v for k, v in r.items() if k != 'screenshot_b64'}, indent=2, default=str))
    except Exception as e:
        import traceback
        print(f'--- RUN {i+1} CRASHED ---')
        traceback.print_exc()
"

echo ""
echo "################################################"
echo "PART 7: ALL TEMPLATE FILES - FULL CONTENT, EVERY REPORT TYPE"
echo "################################################"
find src/revenue_leak_engine/reporting/templates -name "*.html" -exec echo "=== {} ===" \; -exec cat -n {} \;

echo ""
echo "################################################"
echo "PART 8: DEAD CODE / UNWIRED FUNCTIONS - EXHAUSTIVE"
echo "################################################"
grep -oP '^def \K\w+' src/revenue_leak_engine/audit/site_audit.py | while read fn; do
    count=$(grep -c "\b$fn(" src/revenue_leak_engine/audit/site_audit.py)
    echo "$fn: $count occurrence(s)"
done

echo ""
echo "################################################"
echo "PART 9: MODULE ISOLATION - FULL CROSS-REFERENCE"
echo "################################################"
echo "--- Does site_audit.py import anything from geo_audit? ---"
grep -n "^from\|^import" src/revenue_leak_engine/audit/site_audit.py | grep -i geo
echo "--- Does geo_audit.py import anything from site_audit/report_generator? ---"
grep -n "^from\|^import" src/revenue_leak_engine/audit/geo_audit.py | grep -iE "site_audit|report_generator"

echo ""
echo "################################################"
echo "PART 10: GIT - FULL HISTORY WITH STATS"
echo "################################################"
git log --oneline -30
echo "---"
git status
echo "---"
git diff --stat HEAD~20 HEAD 2>/dev/null

echo ""
echo "################################################"
echo "PART 11: ALL TEST FILES - FULL CONTENT"
echo "################################################"
find tests/ -name "*.py" -exec echo "=== {} ===" \; -exec cat -n {} \;

echo ""
echo "################################################"
echo "PART 12: PIPELINE END-TO-END, REAL DOMAINS"
echo "################################################"
rm -rf data/reports/*.html
python -m revenue_leak_engine.pipeline --niche beauty --limit 8 --seed-csv test_seeds.csv 2>&1

echo ""
echo "EXAMINATION COMPLETE"
