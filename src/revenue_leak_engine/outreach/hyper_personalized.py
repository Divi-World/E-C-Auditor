import csv, urllib.parse, httpx, time
from pathlib import Path
from revenue_leak_engine.config import PROJECT_ROOT

def generate_hyper_personalized_outreach():
    leads_dir = PROJECT_ROOT / "data" / "leads"
    if not leads_dir.exists(): return
    drafts = []
    for csv_file in leads_dir.glob("*_leads_ranked.csv"):
        with open(csv_file, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("lead_status") == "QUALIFIED_LEAK":
                    dom = row.get("domain")
                    prompt = "Write a 3-sentence cold email to the CTO of " + dom + ". Mention we noticed structural AI discovery leaks on their site, causing LLMs to ignore them in favor of competitors. Keep it professional, highly technical, and under 50 words."
                    try:
                        url = "https://text.pollinations.ai/" + urllib.parse.quote(prompt) + "?model=openai"
                        with httpx.Client(timeout=20.0) as client:
                            r = client.get(url)
                            if r.status_code == 200 and len(r.text) > 20:
                                drafts.append({"domain": dom, "draft": r.text.strip()})
                    except: pass
                    time.sleep(1)
    out = PROJECT_ROOT / "data" / "outreach" / "hyper_personalized_drafts.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["domain", "draft"])
        w.writeheader()
        w.writerows(drafts)
    print(f"  -> Phase 16 Hyper-Personalized Outreach Generated: {out}")
