import pathlib, sys

print("=" * 60)
print("  SYSTEM FORENSIC AUDIT - GROUND TRUTH ESTABLISHMENT")
print("=" * 60)

files_to_check = {
    'src/revenue_leak_engine/pipeline.py': {
        'must_contain': [
            'query_llm_citation(domain, core_prod_for_llm, sov_data)',
            'PHASE 8: DASHBOARD DATA INJECTION',
            'chart_conn = sqlite3.connect(CACHE_DB)',
            'geo_findings["history_chart_data"]',
        ],
        'must_not_contain': [
            'track_llm_citations(domain, niche)',
            'from revenue_leak_engine.audit.llm_citation_tracker import track_llm_citations',
        ]
    },
    'src/revenue_leak_engine/audit/geo_audit.py': {
        'must_contain': [
            'findings["homepage_html"] = hp_html',
        ],
        'must_not_contain': []
    },
    'src/revenue_leak_engine/audit/llm_citation_tracker.py': {
        'must_contain': [
            'clean_domain = domain.replace',
            'error_signals = [',
        ],
        'must_not_contain': [
            "brand = domain.split('.')[0].replace('-', ' ').title()",
        ]
    }
}

all_pass = True
for fpath, checks in files_to_check.items():
    p = pathlib.Path(fpath)
    if not p.exists():
        print(f"  [MISSING] {fpath}")
        all_pass = False
        continue
    content = p.read_text(encoding='utf-8')
    for pattern in checks['must_contain']:
        if pattern in content:
            print(f"  [PASS] {fpath}: contains '{pattern[:50]}...'")
        else:
            print(f"  [FAIL] {fpath}: MISSING '{pattern[:50]}...'")
            all_pass = False
    for pattern in checks['must_not_contain']:
        if pattern not in content:
            print(f"  [PASS] {fpath}: correctly absent '{pattern[:50]}...'")
        else:
            print(f"  [FAIL] {fpath}: DEAD CODE FOUND '{pattern[:50]}...'")
            all_pass = False

# Check template
template_path = pathlib.Path('src/revenue_leak_engine/templates/geo_report.html')
if template_path.exists():
    tcontent = template_path.read_text(encoding='utf-8')
    if 'history_chart_data' in tcontent:
        print(f"  [PASS] geo_report.html: contains history_chart_data")
    else:
        print(f"  [FAIL] geo_report.html: MISSING history_chart_data")
        all_pass = False
    if 'geoTrendChart' in tcontent:
        print(f"  [PASS] geo_report.html: contains geoTrendChart canvas")
    else:
        print(f"  [FAIL] geo_report.html: MISSING geoTrendChart canvas")
        all_pass = False
else:
    print(f"  [MISSING] {template_path}")
    all_pass = False

# Check test file syntax
test_path = pathlib.Path('tests/test_system_health.py')
if test_path.exists():
    try:
        compile(test_path.read_text(encoding='utf-8'), str(test_path), 'exec')
        print(f"  [PASS] test_system_health.py: syntax valid")
    except SyntaxError as e:
        print(f"  [FAIL] test_system_health.py: SYNTAX ERROR at line {e.lineno}: {e.msg}")
        all_pass = False
else:
    print(f"  [MISSING] {test_path}")

print()
print("=" * 60)
if all_pass:
    print("  VERDICT: ALL CHECKS PASSED")
else:
    print("  VERDICT: FAILURES DETECTED - FIX REQUIRED")
print("=" * 60)
