import json, os, httpx
from pathlib import Path
from revenue_leak_engine.config import PROJECT_ROOT

def dispatch_webhooks():
    url = os.environ.get("RLE_WEBHOOK_URL")
    pr_dir = PROJECT_ROOT / "data" / "pr_payloads"
    if not pr_dir.exists(): return
    manifest = []
    for p_file in pr_dir.glob("*.json"):
        payload = json.loads(p_file.read_text(encoding="utf-8"))
        manifest.append({"file": p_file.name, "domain": payload.get("domain"), "dispatched": False})
        if url:
            try:
                msg = "GEO Revenue Leak Detected. Domain: " + str(payload.get('domain')) + ". Issue: " + str(payload.get('issue_code'))
                httpx.post(url, json={"text": msg, "content": msg}, timeout=10)
                manifest[-1]["dispatched"] = True
            except: pass
    out = PROJECT_ROOT / "data" / "pr_payloads" / "dispatch_manifest.json"
    out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"  -> Phase 17 Dispatch Manifest Generated: {out}")
