import csv
from pathlib import Path
from revenue_leak_engine.config import PROJECT_ROOT

def generate_agency_dashboard():
    leads_dir = PROJECT_ROOT / "data" / "leads"
    if not leads_dir.exists(): return
    csv_files = list(leads_dir.glob("*_leads_ranked.csv"))
    if not csv_files: return

    portfolio = []
    total_leak = 0
    for csv_file in csv_files:
        niche = csv_file.stem.replace("_leads_ranked", "").title()
        with open(csv_file, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                leak = float(row.get("estimated_monthly_leak_usd", 0) or 0)
                total_leak += leak
                portfolio.append({"domain": row.get("domain"), "niche": niche, "geo": float(row.get("geo_score", 0) or 0), "cro": float(row.get("cro_score", 0) or 0), "status": row.get("lead_status", "UNKNOWN")})
    
    rows = ""
    for p in portfolio:
        rows += '<tr><td class="p-3">' + str(p["domain"]) + '</td><td class="p-3">' + str(p["niche"]) + '</td><td class="p-3">' + str(p["geo"]) + '</td><td class="p-3">' + str(p["cro"]) + '</td><td class="p-3">' + str(p["status"]) + '</td></tr>'
        
    leak_str = f"{total_leak:,.0f}"
    html = '<!DOCTYPE html><html><head><title>Agency Matrix</title><script src="https://cdn.tailwindcss.com"></script></head><body class="bg-slate-900 text-white p-8"><h1 class="text-3xl font-bold mb-4">Agency Portfolio Matrix</h1><div class="mb-6 text-xl">Total Portfolio Leak: <span class="text-red-400 font-bold">$' + leak_str + '/mo</span></div><table class="w-full text-left border-collapse"><thead><tr class="border-b border-slate-700"><th class="p-3">Domain</th><th class="p-3">Niche</th><th class="p-3">GEO</th><th class="p-3">CRO</th><th class="p-3">Status</th></tr></thead><tbody class="divide-y divide-slate-800">' + rows + '</tbody></table></body></html>'
    
    out = PROJECT_ROOT / "data" / "reports" / "agency_dashboard.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"  -> Phase 15 Agency Dashboard Generated: {out}")
