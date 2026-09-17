import sqlite3
from pathlib import Path
from revenue_leak_engine.config import PROJECT_ROOT

def run_competitor_benchmark():
    db = PROJECT_ROOT / "data" / "geo_intelligence.db"
    if not db.exists(): return
    conn = sqlite3.connect(db)
    q = "SELECT domain, top_competitor, competitor_schema_count FROM entity_sov_history WHERE top_competitor != 'N/A' ORDER BY timestamp DESC"
    seen, comps = set(), {}
    for r in conn.execute(q):
        if r[0] in seen: continue
        seen.add(r[0])
        comps.setdefault(r[1], {"tenants": [], "schemas": r[2]})["tenants"].append(r[0])
    conn.close()
    
    rows = ""
    for c, d in sorted(comps.items(), key=lambda x: len(x[1]['tenants']), reverse=True)[:10]:
        tenants_str = ", ".join(d["tenants"])
        rows += '<tr><td class="p-3">' + str(c) + '</td><td class="p-3">' + str(len(d["tenants"])) + '</td><td class="p-3">' + tenants_str + '</td><td class="p-3">' + str(d["schemas"]) + '</td></tr>'
        
    html = '<!DOCTYPE html><html><head><title>Competitor Threat Matrix</title><script src="https://cdn.tailwindcss.com"></script></head><body class="bg-slate-900 text-white p-8"><h1 class="text-3xl font-bold mb-6">Cross-Tenant Competitor Threat Matrix</h1><table class="w-full text-left border-collapse"><thead><tr class="border-b border-slate-700"><th class="p-3">Competitor</th><th class="p-3">Tenants Threatened</th><th class="p-3">Affected Domains</th><th class="p-3">Schema Density</th></tr></thead><tbody class="divide-y divide-slate-800">' + rows + '</tbody></table></body></html>'
    
    out = PROJECT_ROOT / "data" / "reports" / "competitor_threat_matrix.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"  -> Phase 14 Competitor Matrix Generated: {out}")
