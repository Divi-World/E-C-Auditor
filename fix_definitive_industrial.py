import sys, re, os

site_path = 'src/revenue_leak_engine/audit/site_audit.py'
gen_path = 'src/revenue_leak_engine/reporting/report_generator.py'

with open(site_path, 'r', encoding='utf-8') as f: site_code = f.read()
with open(gen_path, 'r', encoding='utf-8') as f: gen_code = f.read()

# 1. TTFB Fix (Regex to replace any existing ttfb assignment)
ttfb_pattern = re.compile(r'ttfb\s*=\s*page\.evaluate\(""".*?"""\)', re.DOTALL)
new_ttfb = '''ttfb = page.evaluate("""
            async () => {
                try {
                    if (navigator.serviceWorker) {
                        const regs = await navigator.serviceWorker.getRegistrations();
                        for (let r of regs) { await r.unregister(); }
                    }
                    const start = performance.now();
                    await fetch(window.location.href + (window.location.href.includes('?') ? '&' : '?') + '_ttfb=' + Date.now(), { method: 'GET', cache: 'no-store', credentials: 'omit' });
                    return Math.round(performance.now() - start);
                } catch(e) { return null; }
            }
        """)'''
if ttfb_pattern.search(site_code):
    site_code = ttfb_pattern.sub(new_ttfb, site_code)
    print("1. TTFB Network Probe Fixed (Bypasses SW/Cache)")
else:
    print("⚠ TTFB pattern not found, skipping.")

# 2. Screenshot Blank Screen Fix
old_screenshot_block = '''            shot_path = SCREENSHOTS_DIR / f"{safe}.png"
            page.screenshot(path=str(shot_path), full_page=False)'''
new_screenshot_block = '''            shot_path = SCREENSHOTS_DIR / f"{safe}.png"
            page.screenshot(path=str(shot_path), full_page=False)
            # Anti-Blank Screenshot Fallback
            if os.path.exists(str(shot_path)) and os.path.getsize(str(shot_path)) < 2000:
                page.wait_for_timeout(2000)
                page.screenshot(path=str(shot_path), full_page=False)'''
if old_screenshot_block in site_code and 'Anti-Blank' not in site_code:
    site_code = site_code.replace(old_screenshot_block, new_screenshot_block)
    print("2. Anti-Blank Screenshot Fallback Injected")
else:
    print("⚠ Screenshot block not found or already patched.")

# 3. Phase K Script Bloat Fix (Regex)
bloat_pattern = re.compile(r'script_data\s*=\s*page\.evaluate\(""".*?"""\)', re.DOTALL)
new_bloat = '''script_data = page.evaluate("""
        () => {
            const scripts = [...document.querySelectorAll('script[src]')];
            const total = scripts.length;
            const third_party = scripts.filter(s => !s.src.startsWith(location.origin)).length;
            const resources = performance.getEntriesByType('resource');
            const js_resources = resources.filter(r => r.name.includes('.js') || r.initiatorType === 'script');
            const sorted = js_resources.sort((a, b) => (b.transferSize || 0) - (a.transferSize || 0)).slice(0, 3);
            const top3 = sorted.map(s => {
                try { 
                    const url = new URL(s.name); 
                    const size = s.transferSize ? Math.round(s.transferSize / 1024) + 'KB' : 'cached';
                    return url.hostname.replace('www.', '') + ' (' + size + ')'; 
                } catch(e) { return ''; }
            }).filter(Boolean);
            return { total, third_party, top3 };
        }
    """)'''
if bloat_pattern.search(site_code):
    site_code = bloat_pattern.sub(new_bloat, site_code)
    print("3. Phase K Script Bloat Extraction Fixed")
else:
    print("⚠ Script Bloat pattern not found.")

# 4. Phase L App Map Dictionary Injection (Robust)
if 'app_map = {' not in gen_code:
    target = 'seen_codes = set()'
    if target in gen_code:
        app_map_block = '''
    # PHASE L: PRESCRIPTIVE APP MAPPING
    app_map = {
        "missing_sticky_atc": {"shopify": "Recommended App: 'Sticky Add To Cart' by Codeinmatic.", "woocommerce": "Recommended Plugin: 'WooCommerce Sticky Add to Cart'."},
        "no_cart_drawer": {"shopify": "Recommended App: 'Slide Cart' by Appstle.", "woocommerce": "Recommended Plugin: 'WooCommerce Side Cart'."},
        "missing_product_schema": {"shopify": "Recommended App: 'JSON-LD for SEO' by Ilana Davis.", "woocommerce": "Recommended Plugin: Yoast SEO or RankMath."},
        "no_review_widget": {"shopify": "Recommended App: Judge.me or Okendo.", "woocommerce": "Recommended Plugin: Judge.me or Yotpo."},
        "missing_cross_sell": {"shopify": "Recommended App: 'Frequently Bought Together' by Shopify.", "woocommerce": "Recommended Plugin: 'WooCommerce Frequently Bought Together'."}
    }
'''
        gen_code = gen_code.replace(target, target + app_map_block, 1)
        print("4. Phase L App Map Dictionary Injected")
    else:
        print("⚠ Dictionary target not found.")
else:
    print("✓ App Map Dictionary already exists.")

# 5. Phase L App Logic Injection (Robust)
if 'app_rec not in raw_fix' not in gen_code:
    target_logic = 'raw_fix += where_note'
    if target_logic in gen_code:
        app_logic = '''
                
        # PHASE L: Prescriptive App Recommendations
        if 'app_map' in locals() and code in app_map and platform in app_map[code]:
            app_rec = app_map[code][platform]
            if app_rec not in raw_fix:
                raw_fix += "\\n\\n🚀 " + app_rec'''
        gen_code = gen_code.replace(target_logic, target_logic + app_logic, 1)
        print("5. Phase L App Logic Injected")
    else:
        print("⚠ Logic target not found.")
else:
    print("✓ App Logic already exists.")

with open(site_path, 'w', encoding='utf-8') as f: f.write(site_code)
with open(gen_path, 'w', encoding='utf-8') as f: f.write(gen_code)
print("\nDEFINITIVE INDUSTRIAL PATCHES APPLIED.")
