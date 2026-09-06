"""
Revenue Leak Engine - Enterprise CRM & SMTP Dispatcher
Pushes qualified leads to HubSpot (Free CRM) and queues emails via Resend (Free Tier).
"""
import os
import csv
import json
import urllib.request
import urllib.error
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

HUBSPOT_TOKEN = os.getenv("HUBSPOT_TOKEN")
RESEND_TOKEN = os.getenv("RESEND_TOKEN")
FROM_EMAIL = os.getenv("FROM_EMAIL", "revenue-ops@agency.com")

def push_to_hubspot(domain: str, cro_score: float, leak_usd: int):
    """Creates or updates a Contact/Company in HubSpot Free CRM."""
    if not HUBSPOT_TOKEN or HUBSPOT_TOKEN == "your_hubspot_token_here":
        print(f"[SKIP] HubSpot: No token configured for {domain}")
        return False

    url = "https://api.hubapi.com/crm/v3/objects/contacts"
    headers = {
        "Authorization": f"Bearer {HUBSPOT_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Map CSV data to HubSpot properties
    payload = {
        "properties": {
            "email": f"founder@{domain}", # Placeholder, HubSpot will enrich
            "company": domain,
            "lead_status": "Qualified",
            "cro_score": str(cro_score),
            "estimated_monthly_leak": str(leak_usd),
            "lifecyclestage": "lead"
        }
    }

    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req) as response:
            if response.status in [200, 201]:
                print(f"[OK] HubSpot: Lead {domain} pushed successfully.")
                return True
    except urllib.error.HTTPError as e:
        if e.code == 409:
            print(f"[INFO] HubSpot: Lead {domain} already exists.")
            return True
        print(f"[ERROR] HubSpot API Error for {domain}: {e.code}")
    except Exception as e:
        print(f"[ERROR] HubSpot Connection Failed: {e}")
    return False

def queue_resend_email(to_email: str, domain: str, subject: str, html_body: str):
    """Queues the outreach email via Resend API (Free Tier: 100/day)."""
    if not RESEND_TOKEN or RESEND_TOKEN == "your_resend_token_here":
        print(f"[SKIP] Resend: No token configured for {domain}")
        return False

    url = "https://api.resend.com/emails"
    headers = {
        "Authorization": f"Bearer {RESEND_TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "from": FROM_EMAIL,
        "to": [to_email],
        "subject": subject,
        "html": html_body.replace("\n", "<br>") # Basic text-to-HTML for drafts
    }

    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req) as response:
            if response.status in [200, 201]:
                print(f"[OK] Resend: Email queued for {to_email}.")
                return True
    except urllib.error.HTTPError as e:
        print(f"[ERROR] Resend API Error for {domain}: {e.code} - {e.read().decode()}")
    except Exception as e:
        print(f"[ERROR] Resend Connection Failed: {e}")
    return False

def dispatch(niche: str, max_cro_score: float = 6.0, dry_run: bool = True):
    """Main dispatcher loop."""
    csv_path = Path("data/leads") / f"{niche}_leads_ranked.csv"
    if not csv_path.exists():
        print(f"[ERROR] CSV not found: {csv_path}")
        return

    print(f"--- DISPATCHING {niche.upper()} LEADS ---")
    print(f"Mode: {'DRY RUN (No API calls)' if dry_run else 'LIVE (Pushing to CRM/SMTP)'}")
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            if row.get('lead_status') != 'QUALIFIED_LEAK': continue
            
            try:
                cro = float(row.get('cro_score', 10))
                leak = int(row.get('estimated_monthly_leak_usd', 0))
            except ValueError: continue
            
            if cro <= max_cro_score:
                domain = row['domain']
                draft = row.get('outreach_draft', '')
                subject = f"Telemetry alert: Conversion friction on {domain}"
                
                print(f"\n[>] Processing {domain} (Score: {cro}, Leak: ${leak:,})")
                
                if not dry_run:
                    push_to_hubspot(domain, cro, leak)
                    queue_resend_email(f"founder@{domain}", domain, subject, draft)
                else:
                    print(f"    [DRY RUN] Would push to HubSpot and queue email to founder@{domain}")
                
                count += 1

    print(f"\n[COMPLETE] Processed {count} qualified leads.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="CRM & SMTP Dispatcher")
    parser.add_argument("--niche", default="beauty")
    parser.add_argument("--max-cro", type=float, default=6.0)
    parser.add_argument("--live", action="store_true", help="Execute actual API calls (Default is dry-run)")
    args = parser.parse_args()
    
    dispatch(args.niche, args.max_cro, dry_run=not args.live)
