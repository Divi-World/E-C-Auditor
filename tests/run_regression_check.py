import json
from revenue_leak_engine.audit.geo_audit import audit_geo

DOMAINS = [
    "gymshark.com", "glossier.com", "allbirds.com", "beardbrand.com",
    "ritual.com", "thefarmersdog.com", "id.coach.com", "ascolour.com",
    "beautyitis.com", "universalyums.com", "asics.com", "aruka.com",
]

for domain in DOMAINS:
    try:
        r = audit_geo(domain)
        score = r.get("overall_geo_score")
        conf = r.get("score_confidence")
        platform = r.get("platform_detected", "MISSING")
        n_issues = len(r.get("issues", []))
        print(f"{domain:25} score={score!s:6} conf={conf:10} platform={platform:12} issues={n_issues}")
    except Exception as e:
        print(f"{domain:25} CRASHED: {type(e).__name__}: {e}")
