import re

# ===================== PATCH site_audit.py =====================
site_path = 'src/revenue_leak_engine/audit/site_audit.py'
with open(site_path, 'r', encoding='utf-8') as f:
    site_code = f.read()

changes = []

# 1. EXPAND ATC SELECTOR (Fixes shop.issaonline.com false negative)
old_atc = """ATC_SELECTOR = (
    "button[name='add'], button:has-text('Add to cart'), "
    "button:has-text('Add to Cart'), button:has-text('Add to Bag')"
)"""
new_atc = """ATC_SELECTOR = (
    "button[name='add'], button:has-text('Add to cart'), "
    "button:has-text('Add to Cart'), button:has-text('Add to Bag'), "
    "button:has-text('Buy Now'), button:has-text('Add To Cart'), "
    "input[type='submit'][value*='Add' i], input[type='submit'][value*='Buy' i], "
    "button[type='submit'][class*='cart' i], button[type='submit'][class*='product' i], "
    "[data-add-to-cart], [data-action='add-to-cart'], "
    "form[action*='/cart/add'] button, form[action*='/cart/add'] input[type='submit'], "
    "form[action*='add-to-cart'] button, form[action*='add-to-cart'] input[type='submit'], "
    "a[class*='add-to-cart'], a[class*='add_to_cart'], "
    "button[class*='add-to-cart'], button[class*='add_to_cart'], "
    "[class*='product-form'] button[type='submit'], "
    "[class*='woocommerce'] button[type='submit'][name*='add'], "
    ".single_add_to_cart_button, .add_to_cart_button, "
    "button:has-text('Ajouter au panier'), button:has-text('In den Warenkorb')"
)"""
if old_atc in site_code:
    site_code = site_code.replace(old_atc, new_atc)
    changes.append("ATC_SELECTOR expanded for all platforms")

# 2. ADD DOM STABILITY WAIT after overlay dismissal (Fixes slow-JS sites)
old_overlay_wait = """            if detect_overlay(page).get("blocked"):
                findings["error"] = ("unclosable_overlay - page-level checks skipped "
                                     "to avoid false alarms; mark for manual review")
                browser.close()
                return findings"""
new_overlay_wait = """            if detect_overlay(page).get("blocked"):
                # Last resort: aggressive DOM cleanup before giving up
                try:
                    page.evaluate(\"\"\"() => {
                        document.querySelectorAll('[class*="modal"], [class*="popup"], [class*="overlay"], [class*="dialog"], [id*="modal"], [id*="popup"]').forEach(el => {
                            const cs = getComputedStyle(el);
                            if (cs.position === 'fixed' || cs.position === 'absolute') el.remove();
                        });
                        document.documentElement.style.overflow = '';
                        document.body.style.overflow = '';
                    }\"\"\")
                    page.wait_for_timeout(500)
                except Exception:
                    pass

            if detect_overlay(page).get("blocked"):
                findings["error"] = ("unclosable_overlay - page-level checks skipped "
                                     "to avoid false alarms; mark for manual review")
                browser.close()
                return findings

            # DOM STABILITY: Wait for JS rendering to settle before element queries
            try:
                page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass
            page.wait_for_timeout(1000)"""
if old_overlay_wait in site_code:
    site_code = site_code.replace(old_overlay_wait, new_overlay_wait)
    changes.append("DOM stability wait + aggressive overlay cleanup injected")

# 3. NAVIGATION GUARD (Fixes fecofoods.com.ng context destruction)
old_cart_probe = """            if atc_btn is not None:
                req_before = len(seen_urls)
                dl_before = page.evaluate("() => window.dataLayer ? window.dataLayer.length : 0")
                url_before = page.url
                try:
                    atc_btn.click(timeout=1500)
                    page.wait_for_timeout(1500)
                except Exception:
                    pass"""
new_cart_probe = """            if atc_btn is not None:
                req_before = len(seen_urls)
                try:
                    dl_before = page.evaluate("() => window.dataLayer ? window.dataLayer.length : 0")
                except Exception:
                    dl_before = 0
                url_before = page.url
                try:
                    atc_btn.click(timeout=1500)
                    page.wait_for_timeout(1500)
                except Exception:
                    pass
                # Navigation guard: if page navigated, wait for stability
                try:
                    if page.url != url_before:
                        page.wait_for_load_state("domcontentloaded", timeout=5000)
                except Exception:
                    pass"""
if old_cart_probe in site_code:
    site_code = site_code.replace(old_cart_probe, new_cart_probe)
    changes.append("Navigation guard injected for cart probe")

# 4. FIX dataLayer read after click (wrap in try/except)
old_dl_after = '                dl_after = page.evaluate("() => window.dataLayer ? window.dataLayer.length : 0")'
new_dl_after = """                try:
                    dl_after = page.evaluate("() => window.dataLayer ? window.dataLayer.length : 0")
                except Exception:
                    dl_after = 0"""
if old_dl_after in site_code:
    site_code = site_code.replace(old_dl_after, new_dl_after)
    changes.append("dataLayer read wrapped in try/except")

# 5. ADD WooCommerce/custom discovery URLs
old_discovery = """    discovery_urls = [
        f"https://{domain}/collections/all",
        f"https://{domain}/collections",
        f"https://{domain}/shop",
        f"https://{domain}/catalog",
        f"https://{domain}/product-category",
        f"https://{domain}"
    ]"""
new_discovery = """    discovery_urls = [
        f"https://{domain}/collections/all",
        f"https://{domain}/collections",
        f"https://{domain}/shop",
        f"https://{domain}/catalog",
        f"https://{domain}/product-category",
        f"https://{domain}/products",
        f"https://{domain}/store",
        f"https://{domain}/items",
        f"https://{domain}"
    ]"""
if old_discovery in site_code:
    site_code = site_code.replace(old_discovery, new_discovery)
    changes.append("Discovery URLs expanded")

with open(site_path, 'w', encoding='utf-8') as f:
    f.write(site_code)


# ===================== PATCH popup_handler.py =====================
popup_path = 'src/revenue_leak_engine/audit/popup_handler.py'
with open(popup_path, 'r', encoding='utf-8') as f:
    popup_code = f.read()

# 6. EXPAND COOKIE/CONSENT SELECTORS (Master-level handling)
old_cookie = """COOKIE_SELECTORS = [
    "button:has-text(\\"that's fine\\")",
    'button:has-text("Accept all")',
    'button:has-text("Allow all")',
    'button:has-text("Accept cookies")',
    'button:has-text("Allow cookies")',
    'button:has-text("Agree")',
    'button:has-text("Got it")',
    'button:has-text("I understand")',
    'button:text-is("Ok")',
    'button:text-is("OK")',
    'button:text-is("No")',
]"""
new_cookie = """COOKIE_SELECTORS = [
    "button:has-text(\\"that's fine\\")",
    'button:has-text("Accept all")',
    'button:has-text("Allow all")',
    'button:has-text("Accept cookies")',
    'button:has-text("Allow cookies")',
    'button:has-text("Accept All Cookies")',
    'button:has-text("Accept Cookies")',
    'button:has-text("Agree")',
    'button:has-text("I Agree")',
    'button:has-text("I agree")',
    'button:has-text("Got it")',
    'button:has-text("Got It")',
    'button:has-text("I understand")',
    'button:has-text("I Understand")',
    'button:has-text("Continue")',
    'button:has-text("Dismiss")',
    'button:has-text("Necessary only")',
    'button:has-text("Reject all")',
    'button:has-text("Decline all")',
    'button:has-text("Only necessary")',
    'button:text-is("Ok")',
    'button:text-is("OK")',
    'button:text-is("No")',
    'button:text-is("Yes")',
    'button:text-is("Accept")',
    'button:text-is("Allow")',
    'button:text-is("Close")',
    '[id*="accept" i]',
    '[id*="consent" i] button',
    '[class*="consent"] button[class*="accept" i]',
    '[class*="cookie"] button[class*="accept" i]',
    '[class*="cookie"] button[class*="allow" i]',
    '[class*="gdpr"] button',
    '[data-action="accept"]',
    '[data-action="accept-all"]',
    '.cc-accept', '.cc-dismiss', '.cc-btn',
    '#onetrust-accept-btn-handler',
    '#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll',
    '.js-accept-cookies',
]"""
if old_cookie in popup_code:
    popup_code = popup_code.replace(old_cookie, new_cookie)
    changes.append("COOKIE_SELECTORS expanded to industrial coverage")

# 7. EXPAND CLOSE SELECTORS
old_close_end = """    'button:has-text("Decline")',
]"""
new_close_end = """    'button:has-text("Decline")',
    'button:has-text("Skip")',
    'button:has-text("Continue shopping")',
    'button:has-text("Continue Shopping")',
    'button:has-text("Browse site")',
    'button:has-text("Start shopping")',
    'button:has-text("X")',
    'button:has-text("x")',
    '[class*="dismiss" i]',
    '[class*="modal"] [class*="close" i]',
    '[class*="popup"] [class*="close" i]',
    '[class*="banner"] [class*="close" i]',
    '[class*="newsletter"] [class*="close" i]',
    '[class*="subscribe"] [class*="close" i]',
    '[aria-label="Close dialog"]',
    '[aria-label="Close modal"]',
    '[aria-label="Close popup"]',
]"""
if old_close_end in popup_code:
    popup_code = popup_code.replace(old_close_end, new_close_end)
    changes.append("CLOSE_SELECTORS expanded")

# 8. INCREASE DISMISSAL ROUNDS
popup_code = popup_code.replace('def dismiss_overlays(page, max_rounds: int = 5)', 'def dismiss_overlays(page, max_rounds: int = 8)')

with open(popup_path, 'w', encoding='utf-8') as f:
    f.write(popup_code)

print(f"CRO MASTER PATCH COMPLETE: {len(changes)} upgrades applied.")
for c in changes:
    print(f"  ✓ {c}")
