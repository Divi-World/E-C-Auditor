
import sys, json
sys.path.insert(0, 'src')
from revenue_leak_engine.audit.site_audit import audit_site

print("\n--- EXECUTING RAW AUDIT FOR UNIVERSALYUMS.COM ---")
result = audit_site('universalyums.com')

print("\n--- RAW JSON OUTPUT (VERIFYING SANITIZER DATA) ---")
# Print only the issues to keep it readable
for issue in result.get('issues', []):
    print(json.dumps(issue, indent=2))
    
print("\n--- METADATA ---")
print(f"Load Time: {result.get('load_time_ms')}")
print(f"Context: {result.get('screenshot_context')}")
print(f"Notes: {result.get('notes')}")
