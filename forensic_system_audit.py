import os
import re
import csv
from pathlib import Path

print("="*80)
print("FORENSIC SYSTEM STATE AUDIT (v66.0 BASELINE)")
print("="*80)

# 1. GIT & REPO STATE
print("\n[1] REPO STATE:")
os.system("git log -1 --oneline")
os.system("git status -s")

# 2. CORE LOGIC EXTRACTION
print("\n[2] CORE LOGIC SNAPSHOTS:")
sa_path = Path("src/revenue_leak_engine/audit/site_audit.py")
if sa_path.exists():
    sa_code = sa_path.read_text(encoding="utf-8")
    # Image Logic
    img_match = re.search(r"const (domImgs|imgs|allImgs|bgImgs).*?;", sa_code, re.DOTALL)
    print(f"  Image Selector Logic: {img_match.group(0)[:150] if img_match else 'NOT FOUND'}...")
    
    # Cart Exemption Logic
    if "headless_portal_verified_via_network" in sa_code:
        print("  Headless Portal Note: PRESENT")
    else:
        print("  Headless Portal Note: MISSING")
        
    if 'findings["checks_completed"]["funnel_cart"] = True' in sa_code:
        print("  Cart Exemption Logic: PRESENT")
    else:
        print("  Cart Exemption Logic: MISSING")

vp_path = Path("src/revenue_leak_engine/audit/viewport_profiles.py")
if vp_path.exists():
    vp_code = vp_path.read_text(encoding="utf-8")
    if '"name": "desktop"' in vp_code or "'name': 'desktop'" in vp_code:
        print("  Desktop Profile Name: CORRECTLY MAPPED")
    else:
        print("  Desktop Profile Name: MISSING/MISMATCH (Root cause of Desktop/Mobile label flaw)")

rg_path = Path("src/revenue_leak_engine/reporting/report_generator.py")
if rg_path.exists():
    rg_code = rg_path.read_text(encoding="utf-8")
    if 'profile_name=findings.get("profile_name"' in rg_code:
        print("  Report Generator Profile Mapping: CORRECT")
    else:
        print("  Report Generator Profile Mapping: MISSING/DEFAULTING TO MOBILE")

# 3. GENERATED REPORTS FORENSICS
print("\n[3] GENERATED REPORTS FORENSICS:")
reports_dir = Path("data/reports")
if reports_dir.exists():
    total = 0
    zero_img_flaw = 0
    desktop_mobile_label_flaw = 0
    incomplete_checks = 0
    suppressed_evidence = 0
    
    for p in sorted(reports_dir.glob("*.html")):
        if p.name.endswith("_geo.html"): continue
        total += 1
        raw = p.read_text(encoding="utf-8", errors="ignore")
        
        if "Only 0 images found" in raw:
            zero_img_flaw += 1
            print(f"  [FLAW] {p.name}: 0 Images Reported")
            
        if "_desktop" in p.name and ("Mobile CRO & Conversion Audit" in raw or "simulate real-user mobile conditions" in raw):
            desktop_mobile_label_flaw += 1
            print(f"  [FLAW] {p.name}: Desktop report rendering 'Mobile' label")
            
        if "Visual Evidence Suppressed" in raw:
            suppressed_evidence += 1
            
        checks_match = re.search(r'Checks Completed:\s*(\d+)/13', raw)
        if checks_match:
            checks = int(checks_match.group(1))
            if checks < 13:
                incomplete_checks += 1
                target_match = re.search(r'Target:.*?<a href="([^"]+)"', raw, re.DOTALL)
                target = target_match.group(1) if target_match else "UNKNOWN"
                print(f"  [FLAW] {p.name}: Incomplete ({checks}/13) | Target: {target}")

    print(f"\n  SUMMARY: {total} Total Reports Analyzed")
    print(f"  - 0-Image Flaw: {zero_img_flaw}")
    print(f"  - Desktop/Mobile Label Flaw: {desktop_mobile_label_flaw}")
    print(f"  - Incomplete Checks (<13/13): {incomplete_checks}")
    print(f"  - Suppressed Evidence (WAF/Blank): {suppressed_evidence}")
else:
    print("  [!] No reports directory found.")

# 4. OUTREACH & CSV INTEGRITY
print("\n[4] OUTREACH & CSV INTEGRITY:")
csv_dir = Path("data/leads")
if csv_dir.exists():
    csv_files = list(csv_dir.glob("*.csv"))
    if csv_files:
        csv_path = csv_files[0]
        print(f"  Analyzing: {csv_path.name}")
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fields = reader.fieldnames
            if 'outreach_draft' in fields:
                drafts = 0
                failures = 0
                for row in reader:
                    d = row.get('outreach_draft', '')
                    if d and 'Failed' not in d and len(d) > 50:
                        drafts += 1
                    elif 'Failed' in d:
                        failures += 1
                print(f"  - Valid Outreach Drafts: {drafts}")
                print(f"  - Failed Drafts: {failures}")
            else:
                print("  [FLAW] 'outreach_draft' column MISSING from CSV!")
    else:
        print("  [!] No CSV files found.")
else:
    print("  [!] No leads directory found.")

print("\n" + "="*80)
print("FORENSIC AUDIT COMPLETE. PASTE THIS OUTPUT BACK TO THE ENGINEER.")
print("="*80)
