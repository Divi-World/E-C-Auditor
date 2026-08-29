from pathlib import Path
import re

reports_dir = Path("data/reports")
print("="*70)
print("BANNER PRESENCE VERIFICATION (Mobile + Desktop)")
print("="*70)

for p in sorted(reports_dir.glob("*.html")):
    if p.name.endswith("_geo.html"):
        continue
    raw = p.read_text(encoding="utf-8", errors="ignore")
    has_banner = "ESTIMATED REVENUE LEAK" in raw
    banner_count = raw.count("ESTIMATED REVENUE LEAK")
    report_type = "DESKTOP" if "_desktop" in p.name else "MOBILE "
    status = "✓ BANNER" if has_banner else "✗ MISSING"
    double = " [DOUBLE!]" if banner_count > 1 else ""
    print(f"  {report_type} | {p.name:35} | {status} (count: {banner_count}){double}")

print("="*70)
