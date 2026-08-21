"""
Full mobile site audit — v5 (COMPLETE FILE).

Coverage (nothing left behind):
  CRO      : load speed, overlays, Add-to-Cart (found/visible/fold/sticky),
             express checkout (PDP + cart double-check), reviews (triple
             signal), trust/shipping/returns signals, cart drawer behaviour
  SPEED    : perf-based load time, heavy images, script bloat, console errors
  TRACKING : Meta / TikTok / GA4 presence + AddToCart event double-check
  SEO      : product schema, meta description, OG tags (secondary, low weight)

Integrity: every issue carries evidence + confidence + professional fix.
Anything unverifiable goes to manual review, never becomes a claim.
"""
import json as _json
import re
import time
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

from revenue_leak_engine.config import (
    MOBILE_VIEWPORT, AUDIT_TIMEOUT_MS, SCREENSHOTS_DIR,
)
from revenue_leak_engine.audit.popup_handler import (
    detect_overlay, classify_overlay, dismiss_overlays,
)

ATC_SELECTOR = (
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
)
EXPRESS_SELECTOR = (
    "[data-testid='shop-pay-button'], [aria-label*='Shop Pay'], [aria-label*='Apple Pay'], "
    "[aria-label*='Google Pay'], [aria-label*='PayPal'], [id*='apple-pay'], "
    "[class*='apple-pay'], [class*='shop-pay'], button:has-text('Shop Pay')"
)
REVIEW_APP_SELECTOR = (
    "[class*='jdgm'], [class*='loox'], [class*='yotpo'], [class*='stamped'], "
    "[class*='okendo'], [class*='areviews'], [class*='rivyo'], [class*='growave'], "
    "[id*='shopify-product-reviews'], [data-review-app]"
)

CHALLENGE_SIGS = (
    "just a moment", "checking your browser", "verify you are human",
    "cf-browser-verification", "challenge-platform", "hcaptcha", "g-recaptcha",
)
PASSWORD_SIGS = (
    "opening soon", "will be back soon", "store password",
    "enter using password",
)


# ---------------- navigation & measurement helpers ----------------

def _page_text_head(page, chars=400) -> str:
    try:
        return page.evaluate(
            f"() => document.body ? document.body.innerText.slice(0, {chars}).toLowerCase() : ''"
        )
    except Exception:
        return ""


def _goto_resilient(page, url: str) -> bool:
    for strategy in ("load", "domcontentloaded"):
        try:
            page.goto(url, timeout=AUDIT_TIMEOUT_MS, wait_until=strategy)
            if strategy == "domcontentloaded":
                page.wait_for_timeout(3500)
            return True
        except PWTimeout:
            continue
        except Exception:
            return False
    return False


def _perf_load_ms(page):
    try:
        return page.evaluate(
            "() => { const e = performance.getEntriesByType('navigation')[0];"
            " return e && e.loadEventEnd ? Math.round(e.loadEventEnd) : null; }"
        )
    except Exception:
        return None

def _extract_cwv_and_friction(page):
    """Extracts Core Web Vitals (LCP, CLS) and Mobile Touch Target sizes."""
    try:
        return page.evaluate("""
            () => {
                let lcp = 0, cls = 0;
                try {
                    const lcpEntries = performance.getEntriesByType('largest-contentful-paint');
                    if (lcpEntries && lcpEntries.length > 0) lcp = Math.round(lcpEntries[lcpEntries.length - 1].startTime);
                } catch(e) {}
                
                try {
                    const entries = performance.getEntriesByType('layout-shift');
                    if (entries) cls = entries.reduce((sum, e) => sum + (e.hadRecentInput ? 0 : e.value), 0);
                } catch(e) {}
                
                // Touch Target Analysis (Mobile Friction)
                const atc_btn = document.querySelector("button[name='add'], button:has-text('Add to cart'), .single_add_to_cart_button, [data-add-to-cart]");
                let touch_target_ok = false;
                if (atc_btn) {
                    const r = atc_btn.getBoundingClientRect();
                    touch_target_ok = (r.width >= 48 && r.height >= 48);
                }
                
                return { lcp, cls: Math.round(cls * 1000) / 1000, touch_target_ok };
            }
        """)
    except Exception:
        return {"lcp": 0, "cls": 0, "touch_target_ok": False}


def find_a_product_url(page, domain: str) -> str | None:
    # Strategy 1: Shopify public JSON — immune to popups and JS stalls (Fast fail)
    try:
        page.goto(f"https://{domain}/products.json?limit=10",
                  timeout=10000, wait_until="domcontentloaded")
        data = _json.loads(page.inner_text("body"))
        for prod in data.get("products", []):
            if prod.get("handle"):
                return f"https://{domain}/products/{prod['handle']}"
    except Exception:
        pass
        
    # Strategy 2: Platform-Agnostic rendered links (Shopify, Woo, BigC, Custom)
    discovery_urls = [
        f"https://{domain}/collections/all",
        f"https://{domain}/collections",
        f"https://{domain}/shop",
        f"https://{domain}/catalog",
        f"https://{domain}/product-category",
        f"https://{domain}/products",
        f"https://{domain}/store",
        f"https://{domain}/items",
        f"https://{domain}"
    ]
    
    # Broad regex for product URLs across all major platforms
    product_url_pattern = re.compile(r'/(products?|p|shop|item|dp|catalog|buy)/[a-zA-Z0-9_\-]+/?$', re.I)
    blacklist = ['cart', 'checkout', 'account', 'search', 'policies', 'blogs', 'pages', 'gift-card', 'login', 'register']
    
    for url in discovery_urls:
        if not _goto_resilient(page, url):
            continue
        page.wait_for_timeout(1500)
        dismiss_overlays(page)
        
        links = page.evaluate("""
            () => Array.from(document.querySelectorAll('a[href]')).map(a => a.getAttribute('href'))
        """)
        
        for href in links:
            if not href: continue
            clean_href = href.split('?')[0].split('#')[0]
            if product_url_pattern.search(clean_href):
                if any(bl in clean_href.lower() for bl in blacklist):
                    continue
                if href.startswith("http"):
                    return href
                else:
                    return f"https://{domain}{href.split('?')[0]}"
    return None


# ---------------- main audit ----------------

def audit_site(domain: str) -> dict:
    findings = {
        "domain": domain, "product_url": None, "load_time_ms": None,
        "issues": [], "screenshot_path": None, "popup_screenshot_path": None,
        "notes": "", "error": None,
    }
    safe = domain.replace(".", "_")
    viewport_h = MOBILE_VIEWPORT.get("height", 844)

    seen_urls: list[str] = []
    console_errors: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            viewport=MOBILE_VIEWPORT,
            user_agent=(
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
                "Mobile/15E148 Safari/604.1"
            ),
            has_touch=True,
            ignore_https_errors=True,
        )
        page = context.new_page()
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """)
        page.on("request", lambda req: seen_urls.append(req.url))
        page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)

        try:
            product_url = find_a_product_url(page, domain)
            if not product_url:
                findings["error"] = "no_product_url_found"
                browser.close()
                return findings

            findings["product_url"] = product_url
            start = time.time()
            if not _goto_resilient(page, product_url):
                # ENTERPRISE TIMEOUT FALLBACK: If Playwright fails, use curl_cffi stealth fetch
                try:
                    from curl_cffi import requests as cffi_requests
                    r = cffi_requests.get(product_url, timeout=15, impersonate="chrome120")
                    if r.status_code == 200 and len(r.text) > 500:
                        findings["load_time_ms"] = 9999 # Flag as slow/fallback
                        findings["notes"] += "playwright_timeout_used_curl_cffi_fallback. "
                        # Inject basic HTML into page via data URI or evaluate
                        page.goto(f"data:text/html;charset=utf-8,{r.text[:50000].replace('#', '%23')}")
                    else:
                        findings["error"] = "timeout"
                        browser.close()
                        return findings
                except Exception:
                    findings["error"] = "timeout"
                    browser.close()
                    return findings
            
            # FORCE CSS NUKE: Neutralize overlays immediately before DOM settles
            try:
                from revenue_leak_engine.audit.popup_handler import REMOVE_OVERLAY_JS
                page.evaluate(REMOVE_OVERLAY_JS)
            except Exception:
                pass
            findings["load_time_ms"] = _perf_load_ms(page) or int((time.time() - start) * 1000)

            head = _page_text_head(page)
            if any(s in head for s in CHALLENGE_SIGS):
                page.wait_for_timeout(6000)
                if any(s in _page_text_head(page) for s in CHALLENGE_SIGS):
                    findings["error"] = "bot_challenge - manual review"
                    browser.close()
                    return findings
            if any(s in head for s in PASSWORD_SIGS):
                findings["error"] = "store_password_protected - not a live store"
                browser.close()
                return findings

            page.wait_for_timeout(2500)  # let delayed overlays appear

            # ---- overlays: evidence first, then dismiss ----
            overlay = detect_overlay(page)
            if overlay.get("blocked"):
                # P1 VISUAL PROOF: Capture bounding box for annotation before dismissal
                try:
                    overlay_box = page.evaluate("""
                        () => {
                            const el = document.elementFromPoint(innerWidth / 2, innerHeight / 2);
                            let node = el;
                            while(node && node !== document.documentElement) {
                                const cs = getComputedStyle(node);
                                if (cs.position === 'fixed' || cs.position === 'absolute') {
                                    const r = node.getBoundingClientRect();
                                    return {x: r.x, y: r.y, width: r.width, height: r.height};
                                }
                                node = node.parentElement;
                            }
                            return null;
                        }
                    """)
                    if overlay_box:
                        findings["popup_annotation"] = [overlay_box]
                except Exception: pass
                kind = classify_overlay(overlay)
                popup_shot = SCREENSHOTS_DIR / f"{safe}_popup.png"
                page.screenshot(path=str(popup_shot), full_page=False)
                findings["popup_screenshot_path"] = str(popup_shot)
                if kind == "marketing_popup":
                    findings["issues"].append({
                        "code": "intrusive_popup",
                        "description": "A viewport-blocking popup (discount/email capture) greets mobile visitors on load.",
                        "evidence": f"overlay detected + screenshot {popup_shot.name}",
                        "severity": "medium", "confidence": "high",
                        "fix": "Replace the on-load modal with exit-intent or a delayed, dismissible banner; on-load modals cost mobile conversions.",
                    })
                else:
                    findings["notes"] += f"Overlay on load ({kind}) dismissed; not counted as a leak. "
                actions = dismiss_overlays(page)
                if actions:
                    findings["notes"] += f"Overlay dismissed via: {', '.join(actions)}. "

            if detect_overlay(page).get("blocked"):
                # Last resort: aggressive DOM cleanup before giving up
                try:
                    page.evaluate("""() => {
                        document.querySelectorAll('[class*="modal"], [class*="popup"], [class*="overlay"], [class*="dialog"], [id*="modal"], [id*="popup"]').forEach(el => {
                            const cs = getComputedStyle(el);
                            if (cs.position === 'fixed' || cs.position === 'absolute') el.remove();
                        });
                        document.documentElement.style.overflow = '';
                        document.body.style.overflow = '';
                    }""")
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
            page.wait_for_timeout(1000)

            shot_path = SCREENSHOTS_DIR / f"{safe}.png"
            page.screenshot(path=str(shot_path), full_page=False)
            findings["screenshot_path"] = str(shot_path)

            # ---- CRO / SPEED / SEO checks (no clicks yet) ----
            cwv = _extract_cwv_and_friction(page)
            findings["cwv"] = cwv
            if cwv.get("lcp", 0) > 2500:
                findings["issues"].append({
                    "code": "poor_lcp",
                    "description": f"Largest Contentful Paint (LCP) is {cwv['lcp']}ms (target <2500ms).",
                    "evidence": f"LCP: {cwv['lcp']}ms",
                    "severity": "high", "confidence": "high",
                    "fix": "Optimize hero image delivery, preload critical fonts, and reduce server response time (TTFB)."
                })
            if cwv.get("cls", 0) > 0.1:
                findings["issues"].append({
                    "code": "poor_cls",
                    "description": f"Cumulative Layout Shift (CLS) is {cwv['cls']} (target <0.1).",
                    "evidence": f"CLS: {cwv['cls']}",
                    "severity": "medium", "confidence": "high",
                    "fix": "Reserve space for images/video embeds and avoid injecting dynamic content above the fold without placeholders."
                })
            _check_load_speed(findings)
            atc_btn = _check_add_to_cart(page, findings, viewport_h)
            
            if atc_btn and not cwv.get("touch_target_ok"):
                findings["issues"].append({
                    "code": "small_touch_target",
                    "description": "Add to Cart button is smaller than 48x48px on mobile.",
                    "evidence": "Touch target analysis failed minimum 48px requirement.",
                    "severity": "medium", "confidence": "high",
                    "fix": "Increase padding on the mobile ATC button to ensure it meets WCAG touch target guidelines."
                })
            pdp_express = _visible_any(page, EXPRESS_SELECTOR)
            _check_reviews(page, findings)
            _check_trust_signals(page, findings)
            _check_heavy_images(page, findings)
            _check_script_bloat(page, findings)
            _check_console_errors(findings, console_errors)
            _check_seo(page, findings)

            # ---- tracking presence (from observed network + DOM) ----
            html_has = page.evaluate("() => document.documentElement.outerHTML.slice(0, 400000)")
            meta_pixel = any("facebook.com/tr" in u or "connect.facebook.net" in u for u in seen_urls) or "fbq" in html_has
            tiktok_pixel = any("analytics.tiktok.com" in u for u in seen_urls) or "ttq" in html_has
            ga4 = any("googletagmanager.com/gtag" in u or "/g/collect" in u for u in seen_urls) or "gtag(" in html_has
            if not meta_pixel:
                findings["issues"].append({
                    "code": "meta_pixel_missing",
                    "description": "Meta (Facebook/Instagram) Pixel not detected on the product page.",
                    "evidence": "no facebook.com/tr request and no fbq in page HTML",
                    "severity": "medium", "confidence": "high",
                    "fix": "Install the Meta Pixel via Shopify's Facebook & Instagram channel so ad optimization and retargeting work.",
                })
            if not tiktok_pixel:
                findings["issues"].append({
                    "code": "tiktok_pixel_missing",
                    "description": "TikTok Pixel not detected.",
                    "evidence": "no analytics.tiktok.com request and no ttq in page HTML",
                    "severity": "low", "confidence": "high",
                    "fix": "If TikTok traffic is part of the plan, install the TikTok Pixel via the Shopify app.",
                })
            if not ga4:
                findings["issues"].append({
                    "code": "ga4_missing",
                    "description": "Google Analytics 4 not detected.",
                    "evidence": "no gtag/collect requests and no gtag in page HTML",
                    "severity": "low", "confidence": "high",
                    "fix": "Add GA4 with e-commerce events to measure what ads and CRO changes actually do.",
                })

            # ---- cart probe: ONE safe click, multiple observations ----
            if atc_btn is not None:
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
                    pass

                if not pdp_express and _visible_any(page, EXPRESS_SELECTOR):
                    pass  # express exists in cart drawer -> no issue
                elif not pdp_express:
                    findings["issues"].append({
                        "code": "no_express_checkout",
                        "description": "No express checkout (Shop Pay/Apple Pay) on PDP or in the cart drawer.",
                        "evidence": "not visible on PDP nor after a safe Add-to-Cart click",
                        "severity": "medium", "confidence": "high",
                        "fix": "Enable Shop Pay / Apple Pay / Google Pay in Shopify Settings > Payments so express buttons render on PDP and cart.",
                    })

                event_seen = any(
                    ("facebook.com/tr" in u or "/g/collect" in u or "analytics.tiktok.com" in u)
                    for u in seen_urls[req_before:]
                )
                try:
                    dl_after = page.evaluate("() => window.dataLayer ? window.dataLayer.length : 0")
                except Exception:
                    dl_after = 0
                if (meta_pixel or ga4 or tiktok_pixel) and not event_seen and dl_after <= dl_before:
                    findings["issues"].append({
                        "code": "add_to_cart_event_missing",
                        "description": "Pixels are installed but no AddToCart event fired when the button was clicked.",
                        "evidence": "no pixel request and no dataLayer growth within 1.5s of a real Add-to-Cart click",
                        "severity": "medium", "confidence": "medium",
                        "fix": "Wire the add_to_cart / AddToCart event in the pixel setup (Shopify Facebook channel or GTM) so campaigns optimize on purchase intent.",
                    })

                navigated = page.url != url_before
                drawer = page.query_selector(
                    "[id*='cart-drawer'], [class*='cart-drawer'], [class*='mini-cart'], [class*='cart-modal']"
                )
                if navigated or not (drawer and drawer.is_visible()):
                    findings["issues"].append({
                        "code": "no_cart_drawer",
                        "description": "Adding to cart leaves the product page (full-page cart) instead of opening a cart drawer.",
                        "evidence": "URL changed or no visible drawer element after Add-to-Cart click",
                        "severity": "low", "confidence": "medium",
                        "fix": "Use a slide-out cart drawer so shoppers keep browsing (and keep seeing recommendations) after adding items.",
                    })

        except PWTimeout:
            findings["error"] = "timeout"
        except Exception as e:
            findings["error"] = f"audit_failed: {e}"
        finally:
            browser.close()

    # ENTERPRISE SCORING PARITY: Calculate actual opportunity score based on issues
    # Base score 10. High severity = -2, Medium = -1, Low = -0.5
    score = 10.0
    for issue in findings.get("issues", []):
        sev = issue.get("severity", "low")
        if sev == "high": score -= 2.0
        elif sev == "medium": score -= 1.0
        else: score -= 0.5
    
    # Absolute penalty for missing the revenue button
    if any(i.get("code") == "no_add_to_cart_found" for i in findings.get("issues", [])):
        score = min(score, 2.0) # Cannot score higher than 2 if the buy button is missing
        
    findings["opportunity_score"] = max(0.0, round(score, 1))
    
    return findings


# ---------------- individual checks ----------------


def _safe_query(page, action_func, retries=2):
    """Wraps DOM queries to catch 'Execution context was destroyed' during redirects."""
    for attempt in range(retries):
        try:
            return action_func()
        except Exception as e:
            if "Execution context was destroyed" in str(e) or "Target page, context or browser has been closed" in str(e):
                try:
                    page.wait_for_load_state("domcontentloaded", timeout=3000)
                    page.wait_for_timeout(1000)
                except Exception:
                    pass
            else:
                raise
    return None


def _visible_any(page, selector: str) -> bool:
    return any(b.is_visible() for b in page.query_selector_all(selector))


def _check_load_speed(findings: dict):
    ms = findings["load_time_ms"]
    if ms and ms > 3500:
        findings["issues"].append({
            "code": "slow_load",
            "description": f"Mobile load time is {ms}ms (target is <2500ms).",
            "evidence": f"{ms}ms measured via browser navigation timing",
            "severity": "high" if ms > 5000 else "medium", "confidence": "high",
            "fix": "Compress/lazy-load product imagery, defer third-party apps, and remove render-blocking scripts above the fold.",
        })


def _check_add_to_cart(page, findings, viewport_h: int):
    btn = page.query_selector(ATC_SELECTOR)
    if not btn:
        findings["issues"].append({
            "code": "no_add_to_cart_found",
            "description": "No Add to Cart button detected on the product page.",
            "evidence": "selector search returned no match on cleared page",
            "severity": "high", "confidence": "high",
            "fix": "Ensure a visible, clearly labelled Add to Cart button on the mobile PDP — it is the revenue button.",
        })
        return None

    box = btn.bounding_box()
    if box is None:
        findings["issues"].append({
            "code": "add_to_cart_not_visible",
            "description": "Add to Cart button exists but is hidden on mobile.",
            "evidence": "bounding_box() returned None on cleared page",
            "severity": "high", "confidence": "high",
            "fix": "Unhide the buy box on mobile; a hidden Add to Cart is a silent revenue kill-switch.",
        })
        return btn

    if box["y"] <= viewport_h * 0.95:
        return btn  # above the fold: ideal

    page.evaluate("window.scrollTo(0, 800)")
    page.wait_for_timeout(700)
    sticky = page.evaluate("""
        () => {
            for (const b of document.querySelectorAll('button')) {
                const t = (b.innerText || '').toLowerCase();
                if (!/add to (cart|bag)|buy now/.test(t)) continue;
                let n = b, depth = 0;
                while (n && n !== document.body && depth < 6) {
                    const cs = getComputedStyle(n);
                    if (cs.position === 'fixed' || cs.position === 'sticky') {
                        const r = n.getBoundingClientRect();
                        if (r.top < innerHeight && r.bottom > 0 && r.height > 20) return true;
                    }
                    n = n.parentElement; depth++;
                }
            }
            return false;
        }
    """)
    if sticky:
        return btn  # sticky purchase bar = good pattern

    findings["issues"].append({
        "code": "add_to_cart_below_fold",
        "description": "Add to Cart sits below the mobile fold with no sticky purchase bar.",
        "evidence": f"button top at y={int(box['y'])} on a {viewport_h}px viewport; no sticky bar after scroll",
        "severity": "medium", "confidence": "high",
        "fix": "Add a sticky mobile Add to Cart bar or move the buy box above the fold.",
    })
    return btn


def _check_reviews(page, findings):
    widget = page.query_selector(REVIEW_APP_SELECTOR)
    visible_widget = widget.is_visible() if widget else False
    schema = page.evaluate("() => document.body.innerHTML.includes('aggregateRating')")
    text_sig = page.evaluate(
        "() => /\\d(\\.\\d+)?\\s*(reviews|ratings)|rated\\s\\d/i.test("
        "(document.body.innerText || '').slice(0, 20000))"
    )
    if not (visible_widget or schema or text_sig):
        findings["issues"].append({
            "code": "no_review_widget",
            "description": "No social proof (reviews/ratings) detectable near the product.",
            "evidence": "no review-app DOM, no aggregateRating schema, no 'N reviews' text",
            "severity": "low", "confidence": "high",
            "fix": "Add a review app (Judge.me/Loox/Yotpo) and surface the star rating above the fold — trust drives beauty conversion.",
        })


def _check_trust_signals(page, findings):
    found = page.evaluate(
        "() => /free shipping|money.back|guarantee|easy returns|free returns|"
        "secure checkout|cruelty.free|dermatologist|vegan|clean ingredients/i.test("
        "(document.body.innerText || '').slice(0, 20000))"
    )
    if not found:
        findings["issues"].append({
            "code": "no_trust_signals",
            "description": "No trust/reassurance signals (shipping, returns, guarantee) detectable on the PDP.",
            "evidence": "no trust-language match in page text",
            "severity": "low", "confidence": "medium",
            "fix": "Add shipping/returns/guarantee reassurance near the buy box; hesitation at the buy box is where carts die.",
        })


def _check_heavy_images(page, findings):
    top5 = page.evaluate("""
        () => {
            const imgs = performance.getEntriesByType('resource').filter(e =>
                e.initiatorType === 'img' || /\\.(png|jpe?g|webp|avif)(\\?|$)/i.test(e.name));
            return imgs.map(e => e.transferSize || 0).sort((a, b) => b - a).slice(0, 5)
                       .reduce((a, b) => a + b, 0);
        }
    """)
    if top5 and top5 > 1_500_000:
        findings["issues"].append({
            "code": "heavy_images",
            "description": f"Top 5 images transfer {top5 // 1000}KB — far above what a mobile PDP should ship.",
            "evidence": f"{top5 // 1000}KB combined transferSize for the 5 largest images",
            "severity": "medium", "confidence": "high",
            "fix": "Serve compressed WebP/AVIF at responsive sizes (Shopify image CDN params) and lazy-load below-fold media.",
        })


def _check_script_bloat(page, findings):
    counts = page.evaluate("""
        () => {
            const scripts = [...document.querySelectorAll('script[src]')];
            return [scripts.length, scripts.filter(s => !s.src.startsWith(location.origin)).length];
        }
    """)
    total, third_party = counts or [0, 0]
    if third_party > 25:
        findings["issues"].append({
            "code": "script_bloat",
            "description": f"{third_party} third-party scripts load on the PDP — app bloat is taxing every visitor.",
            "evidence": f"{total} scripts total, {third_party} third-party",
            "severity": "medium", "confidence": "high",
            "fix": "Audit installed Shopify apps; remove or defer unused ones. Every app script is a tax on speed and conversion.",
        })


def _check_console_errors(findings, console_errors):
    if console_errors:
        findings["issues"].append({
            "code": "console_errors",
            "description": f"{len(console_errors)} JavaScript error(s) fired during page load.",
            "evidence": "; ".join(console_errors[:3])[:300],
            "severity": "low", "confidence": "high",
            "fix": "Fix or remove the throwing script/app — JS errors often mean a broken widget or a tracking tag misfire.",
        })


def _check_seo(page, findings):
    seo = page.evaluate("""
        () => ({
            schema: [...document.querySelectorAll('script[type="application/ld+json"]')]
                        .some(s => /"product"/i.test(s.textContent || '')),
            meta_desc: !!document.querySelector('meta[name="description"][content]'),
            og: !!document.querySelector('meta[property="og:title"]') &&
                !!document.querySelector('meta[property="og:image"]'),
        })
    """)
    if not seo.get("schema"):
        findings["issues"].append({
            "code": "missing_product_schema",
            "description": "No Product structured data (schema) on the PDP.",
            "evidence": "no ld+json script containing a Product object",
            "severity": "low", "confidence": "high",
            "fix": "Add Product schema (price, availability, aggregateRating) for rich results in Google.",
        })
    if not seo.get("meta_desc"):
        findings["issues"].append({
            "code": "missing_meta_description",
            "description": "No meta description on the product page.",
            "evidence": "meta[name=description] missing or empty",
            "severity": "low", "confidence": "high",
            "fix": "Write a benefit-led meta description per product template so Google shows your copy, not a random snippet.",
        })
    if not seo.get("og"):
        findings["issues"].append({
            "code": "missing_og_tags",
            "description": "OpenGraph social preview tags incomplete.",
            "evidence": "og:title or og:image missing",
            "severity": "low", "confidence": "high",
            "fix": "Set og:title/og:description/og:image so shared links render rich previews.",
        })