python -m py_compile src/revenue_leak_engine/audit/site_audit.py && python -m py_compile src/revenue_leak_engine/reporting/report_generator.py && export PYTHONPATH=src && python -m revenue_leak_engine.pipeline --niche beauty --limit 8 --seed-csv test_seeds.csv


Run the above command for the CRO to audit the site and generate report.