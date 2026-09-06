# CRO Engine Runbook

## Setup

```bash
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
export PYTHONPATH=src
export PYTHONIOENCODING=utf-8

python -m py_compile src/revenue_leak_engine/audit/site_audit.py && python -m py_compile src/revenue_leak_engine/reporting/report_generator.py && export PYTHONPATH=src && python -m revenue_leak_engine.pipeline --niche beauty --limit 8 --seed-csv test_seeds.csv


Run the above command for the CRO to audit the site and generate report.

Validate System
python -m compileall -q src/
PYTHONPATH=src python -m pytest tests/ -q

Outreach Live Run
Requires valid .env and verified Resend sender domain.
PYTHONPATH=src python src/revenue_leak_engine/outreach/crm_dispatcher.py --niche beauty --live

Direct Single-Site CRO Audit
PYTHONPATH=src python -c "from revenue_leak_engine.audit.site_audit import audit_site; import json; print(json.dumps(audit_site('gymshark.com'), indent=2, default=str))"

Critical Files
src/revenue_leak_engine/audit/site_audit.py
src/revenue_leak_engine/audit/revenue_math.py
src/revenue_leak_engine/audit/geo_audit.py
src/revenue_leak_engine/pipeline.py
src/revenue_leak_engine/reporting/report_generator.py
src/revenue_leak_engine/reporting/templates/report.html
src/revenue_leak_engine/outreach/email_generator.py
src/revenue_leak_engine/outreach/crm_dispatcher.py


