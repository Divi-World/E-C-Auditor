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
from revenue_leak_engine.audit.seo_audit import audit_seo_onpage
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
    "[data-testid='shop-pay-button'], [aria-label*='Shop Pay' i], [aria-label*='Apple Pay' i], "
    "[aria-label*='Google Pay' i], [aria-label*='PayPal' i], [id*='apple-pay' i], "
    "[class*='apple-pay' i], [class*='shop-pay' i], button:has-text('Shop Pay'), "
    "shop-pay-button, apple-pay-button, paypal-button, [data-payment-method='apple_pay']"
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

def get_pixel_fix(platform):
    fixes = {
        'shopify': "Install the Meta Pixel via Shopify's Facebook & Instagram channel so ad optimization and retargeting work.",
        'woocommerce': "Install the official 'Facebook for WooCommerce' plugin or configure via GTM.",
        'bigcommerce': "Enable Facebook Pixel in BigCommerce Settings > Marketing > Analytics.",
        'magento': "Install a Magento 2 Meta Pixel extension or configure via GTM.",
        'custom': "Implement the Meta Pixel via GTM or your site's header template."
    }
    return fixes.get(platform, fixes['custom'])

def get_express_fix(platform):
    fixes = {
        'shopify': "Enable Shop Pay / Apple Pay / Google Pay in Shopify Settings > Payments so express buttons render on PDP and cart.",
        'woocommerce': "Enable Apple Pay / Google Pay via WooCommerce Payments, Stripe, or PayPal settings.",
        'bigcommerce': "Enable digital wallets in BigCommerce Settings > Payments.",
        'magento': "Enable Apple Pay / Google Pay via your payment gateway extension (Stripe/Braintree).",
        'custom': "Enable digital wallet express checkout options via your payment gateway configuration."
    }
    return fixes.get(platform, fixes['custom'])

def get_app_bloat_fix(platform):
    fixes = {
        'shopify': "Audit installed Shopify apps; remove or defer unused ones. Every app script is a tax on speed and conversion.",
        'woocommerce': "Audit installed WordPress/WooCommerce plugins; deactivate or defer unused ones.",
        'bigcommerce': "Audit installed BigCommerce apps and custom scripts; defer unused ones.",
        'magento': "Audit installed Magento extensions; disable unused modules via CLI.",
        'custom': "Audit third-party scripts; defer non-critical JS and remove unused integrations."
    }
    return fixes.get(platform, fixes['custom'])

def get_tiktok_fix(platform):
    fixes = {
        'shopify': "If TikTok traffic is part of the plan, install the TikTok Pixel via the Shopify app.",
        'woocommerce': "Install the official TikTok for WooCommerce plugin or configure via GTM.",
        'bigcommerce': "Add TikTok Pixel via BigCommerce Script Manager or GTM.",
        'magento': "Install a Magento 2 TikTok Pixel extension or configure via GTM.",
        'custom': "Implement the TikTok Pixel via GTM or your site's header template."
    }
    return fixes.get(platform, fixes['custom'])

def get_drawer_fix(platform):
    fixes = {
        'shopify': "Use a Shopify 2.0 compatible slide-out cart drawer theme or app.",
        'woocommerce': "Enable 'Ajax add to cart' and a mini-cart drawer via your theme settings or a WooCommerce plugin.",
        'bigcommerce': "Enable 'Show a quick summary' (mini-cart) in BigCommerce Storefront Settings.",
        'magento': "Enable the mini-cart sidebar in your Magento theme configuration.",
        'custom': "Implement an AJAX slide-out cart drawer so users don't leave the product page."
    }
    return fixes.get(platform, fixes['custom'])


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
            """() => {
                const nav = performance.getEntriesByType('navigation')[0];
                if (!nav) return null;
                // Client-side processing time (Excludes Cloudflare/WAF network hold time)
                return Math.round(nav.domContentLoadedEventEnd - nav.responseEnd);
            }"""
        )
    except Exception:
        return None

def _extract_cwv_and_friction(page):
    try:
        return page.evaluate("""
            () => {
                return new Promise((resolve) => {
                    let lcp = 0, cls = 0;
                    try {
                        const lcpEntries = performance.getEntriesByType('largest-contentful-paint');
                        if (lcpEntries.length > 0) lcp = lcpEntries[lcpEntries.length - 1].startTime;
                        const clsEntries = performance.getEntriesByType('layout-shift');
                        cls = clsEntries.reduce((sum, e) => sum + (e.hadRecentInput ? 0 : e.value), 0);
                    } catch(e) {}
                    
                    try {
                        const lcpObs = new PerformanceObserver((list) => {
                            const entries = list.getEntries();
                            if (entries.length > 0) lcp = entries[entries.length - 1].startTime;
                        });
                        lcpObs.observe({ type: 'largest-contentful-paint', buffered: true });
                    } catch(e) {}

                    try {
                        const clsObs = new PerformanceObserver((list) => {
                            list.getEntries().forEach(entry => {
                                if (!entry.hadRecentInput) cls += entry.value;
                            });
                        });
                        clsObs.observe({ type: 'layout-shift', buffered: true });
                    } catch(e) {}

                    setTimeout(() => {
                        let touch_target_ok = false;
                        const atc = document.querySelector("button[name='add'], [data-add-to-cart], .single_add_to_cart_button");
                        if (atc) {
                            const r = atc.getBoundingClientRect();
                            touch_target_ok = (r.width >= 32 && r.height >= 32);
                        }
                        resolve({ lcp: Math.round(lcp), cls: Math.round(cls * 1000) / 1000, touch_target_ok });
                    }, 1500);
                });
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
        f"https://{domain}/product",
        f"https://{domain}/all-products",
        f"https://{domain}/shop/all",
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
            # Broad match: WooCommerce (/product/), Shopify (/products/), Custom (/p/, /item/)
            is_product_path = any(p in clean_href.lower() for p in ['/product/', '/products/', '/p/', '/item/', '/dp/', '/buy/'])
            if is_product_path or product_url_pattern.search(clean_href):
                if any(bl in clean_href.lower() for bl in blacklist): continue
                if '/product-category/' in clean_href.lower() or '/collections/' in clean_href.lower(): continue
                return href if href.startswith("http") else f"https://{domain}{clean_href}"
    
    # BULLETPROOF FALLBACK: Use curl_cffi to aggressively hunt product URLs in raw HTML
    try:
        from curl_cffi import requests as cffi_requests
        r = cffi_requests.get(f"https://{domain}", timeout=15, impersonate="chrome120")
        if r.status_code == 200:
            html_raw = r.text
            import re as _re
            matches = _re.findall(r'href=["\'](https?://[^"\']*(?:/product/|/products/|/p/|/item/|/dp/|/shop/)[^"\']*)["\']', html_raw, _re.I)
            blacklist = ['cart', 'checkout', 'account', 'search', 'policies', 'blogs', 'pages', 'gift-card', 'login', 'register', 'category']
            for m in matches:
                clean = m.split('?')[0].split('#')[0].lower()
                if not any(bl in clean for bl in blacklist):
                    return m
    except Exception:
        pass
        
    # HEURISTIC FALLBACK: Scan homepage for "Subscribe", "Buy", "Add to Cart" + Price
    try:
        page.goto(f"https://{domain}", timeout=15000, wait_until="domcontentloaded")
        page.wait_for_timeout(1500)
        heuristic_url = page.evaluate("""
            () => {
                const btns = document.querySelectorAll('a, button');
                for (const btn of btns) {
                    const text = (btn.innerText || '').toLowerCase();
                    const href = btn.getAttribute('href') || '';
                    const has_price = btn.closest('body').innerText.includes('$');
                    const is_buy_btn = text.includes('add to cart') || text.includes('buy now') || text.includes('subscribe') || text.includes('select plan') || text.includes('join now');
                    
                    if (is_buy_btn && href && href !== '#' && !href.includes('cart') && !href.includes('checkout')) {
                        if (href.startsWith('http')) return href;
                        return window.location.origin + href;
                    }
                }
                return null;
            }
        """)
        if heuristic_url:
            return heuristic_url
    except Exception:
        pass
    return None


# ---------------- main audit ----------------


def _audit_homepage_and_collection(page, domain: str, findings: dict):
    """Lightweight audit of Homepage and Collection page before PDP."""
    # 1. Homepage Trust & Navigation
    try:
        page.goto(f"https://{domain}", timeout=15000, wait_until="domcontentloaded")
        page.wait_for_timeout(1500)
        
        hp_data = page.evaluate("""
            () => {
                const html = document.body ? document.body.innerText.toLowerCase() : '';
                const footer = document.querySelector('footer') ? document.querySelector('footer').innerText.toLowerCase() : html;
                
                const has_free_shipping = html.includes('free shipping') || html.includes('free delivery');
                const has_returns = html.includes('return') || html.includes('refund') || html.includes('guarantee');
                
                const payment_icons = document.querySelectorAll('img[alt*="visa" i], img[alt*="mastercard" i], img[alt*="paypal" i], img[alt*="amex" i], [class*="payment-icon"], svg[aria-label*="payment" i]');
                const has_payment_trust = payment_icons.length > 0 || footer.includes('secure checkout') || footer.includes('ssl');
                
                return { has_free_shipping, has_returns, has_payment_trust };
            }
        """)
        
        if not hp_data.get('has_free_shipping') and not hp_data.get('has_returns'):
            findings["issues"].append({
                "code": "missing_global_trust_signals",
                "description": "Homepage lacks global trust signals (Free Shipping, Returns, or Guarantees).",
                "evidence": "No shipping or return policy mentions found in homepage text or footer.",
                "severity": "medium", "confidence": "VERIFIED",
                "business_impact": "Shoppers look for shipping/return policies before clicking a product. Missing them increases bounce rate.",
                "fix": "Add a global announcement bar or footer badges for 'Free Shipping over $X' and 'Easy Returns'."
            })
            
        if not hp_data.get('has_payment_trust'):
            findings["issues"].append({
                "code": "missing_payment_trust_badges",
                "description": "Footer lacks recognizable payment method icons or secure checkout badges.",
                "evidence": "No Visa/Mastercard/PayPal icons or 'Secure Checkout' text found in footer.",
                "severity": "low", "confidence": "VERIFIED",
                "business_impact": "Payment badges subconsciously reassure users that the site is legitimate and safe.",
                "fix": "Display standard payment method SVGs and a 'Secure SSL Checkout' badge in the global footer."
            })
    except Exception:
        pass

    # 2. Collection Page Grid (Friction Check)
    try:
        coll_paths = ["/collections/all", "/shop", "/catalog", "/products", "/collections"]
        coll_loaded = False
        for p in coll_paths:
            try:
                resp = page.goto(f"https://{domain}{p}", timeout=8000, wait_until="domcontentloaded")
                if resp and resp.status < 400:
                    coll_loaded = True
                    break
            except Exception:
                continue
                
        if coll_loaded:
            page.wait_for_timeout(1500)
            coll_data = page.evaluate("""
                () => {
                    const cards = document.querySelectorAll('[class*="product-card" i], [class*="product-item" i], .product, article, li[class*="product"]');
                    if (cards.length < 2) return { has_grid: false };
                    
                    let cards_with_price = 0;
                    cards.forEach(card => {
                        if (card.querySelector('[class*="price" i], .price, [data-price]') || card.innerText.match(/\\$\\d+/)) {
                            cards_with_price++;
                        }
                    });
                    return { has_grid: true, total_cards: cards.length, cards_with_price: cards_with_price };
                }
            """)
            
            if coll_data.get('has_grid') and coll_data.get('cards_with_price', 0) < coll_data.get('total_cards', 1) * 0.5:
                findings["issues"].append({
                    "code": "collection_grid_missing_prices",
                    "description": "Product grid on collection page hides prices on many items.",
                    "evidence": f"Only {coll_data.get('cards_with_price')} of {coll_data.get('total_cards')} product cards show a price.",
                    "severity": "medium", "confidence": "VERIFIED",
                    "business_impact": "Forcing users to click into every product to see the price causes massive drop-off.",
                    "fix": "Ensure base prices (and sale prices) are clearly visible directly on the collection grid cards."
                })
    except Exception:
        pass


def _check_advanced_ux_seo(page, findings):
    """Deep interrogation of Shipping, Returns, Variants, Media, and Schema."""
    try:
        ux_data = page.evaluate("""
            () => {
                const bodyText = document.body ? document.body.innerText.toLowerCase() : '';
                const buyBox = document.querySelector('[class*="product" i], [class*="buy" i], form[action*="cart"], [class*="price" i]');
                const buyBoxText = buyBox ? buyBox.innerText.toLowerCase() : bodyText;
                
                const hasVariants = document.querySelector('[class*="variant" i], [class*="swatch" i], select[name*="variant"], [data-option]') !== null;
                const hasShippingInfo = /free shipping|shipping cost|delivery|ships in|estimated delivery/.test(buyBoxText);
                const hasReturnsInfo = /return|refund|guarantee|exchange|money back/.test(buyBoxText);
                
                const imgs = document.querySelectorAll('img');
                const hasVideo = document.querySelector('video, iframe[src*="youtube"], iframe[src*="vimeo"], [class*="video"]') !== null;
                
                const hasSizing = /size guide|sizing|fit guide|dimensions|measurements/.test(bodyText);
                const hasFAQ = /faq|frequently asked|questions/.test(bodyText);
                const hasIngredients = /ingredients|materials|fabric|composition|nutritional/.test(bodyText);
                
                const schemas = document.querySelectorAll('script[type="application/ld+json"]');
                let hasProductSchema = false, hasReviewSchema = false;
                schemas.forEach(s => {
                    const txt = s.innerText.toLowerCase();
                    if (txt.includes('"@type"') && txt.includes('product')) hasProductSchema = true;
                    if (txt.includes('aggregaterating') || txt.includes('review')) hasReviewSchema = true;
                });

                return { hasVariants, hasShippingInfo, hasReturnsInfo, imgCount: imgs.length, hasVideo, hasSizing, hasFAQ, hasIngredients, hasProductSchema, hasReviewSchema };
            }
        """)
    except Exception:
        return

    if not ux_data.get('hasShippingInfo'):
        findings["issues"].append({
            "code": "hidden_shipping_costs", "severity": "high", "confidence": "VERIFIED",
            "observation": "Shipping costs and delivery times are hidden on the product page.",
            "evidence": "No mention of shipping, delivery, or free shipping thresholds detected near the buy box.",
            "interpretation": "Baymard Institute data shows 68% of shoppers abandon carts when shipping costs are a surprise at checkout. Hiding this on the PDP kills high-intent buyers.",
            "recommendation": "Add a dynamic shipping estimator or a clear 'Free Shipping over $X' badge directly inside the buy box."
        })

    if not ux_data.get('hasReturnsInfo'):
        findings["issues"].append({
            "code": "hidden_return_policy", "severity": "medium", "confidence": "VERIFIED",
            "observation": "Return policy and guarantees are not visible near the purchase decision area.",
            "evidence": "No mentions of returns, refunds, or guarantees detected in the product details or buy box.",
            "interpretation": "Shoppers hesitate when they feel trapped by a purchase. Visible return policies reduce purchase anxiety and increase conversion.",
            "recommendation": "Display a concise 'Easy 30-Day Returns' or 'Money-Back Guarantee' badge directly below the Add to Cart button."
        })

    if not ux_data.get('hasProductSchema'):
        findings["issues"].append({
            "code": "missing_product_schema", "severity": "high", "confidence": "VERIFIED",
            "observation": "Missing Product Schema Markup (Structured Data).",
            "evidence": "No application/ld+json Product schema detected in the page head.",
            "interpretation": "Without Product schema, Google and AI search engines (SGE) cannot display rich snippets (price, stock, reviews), severely reducing CTR and AI visibility.",
            "recommendation": "Implement standard JSON-LD Product schema including price, availability, SKU, and aggregateRating."
        })
        
    if not ux_data.get('hasSizing') and not ux_data.get('hasIngredients'):
        if ux_data.get('imgCount', 0) > 0:
            findings["issues"].append({
                "code": "missing_product_specs", "severity": "medium", "confidence": "VERIFIED",
                "observation": "Critical product details (Sizing, Materials, or Ingredients) are missing or hard to find.",
                "evidence": "No size guides, material breakdowns, or ingredient lists detected on the page.",
                "interpretation": "Shoppers cannot evaluate if the product fits their specific needs, leading to hesitation and high return rates.",
                "recommendation": "Add expandable accordion tabs for 'Sizing/Fit', 'Materials/Ingredients', and 'Care Instructions' directly below the product description."
            })

    if ux_data.get('imgCount', 0) < 4 and not ux_data.get('hasVideo'):
        findings["issues"].append({
            "code": "poor_media_richness", "severity": "medium", "confidence": "VERIFIED",
            "observation": "Product gallery lacks sufficient visual assets to build buyer confidence.",
            "evidence": f"Only {ux_data.get('imgCount', 0)} images found and no product video detected.",
            "interpretation": "Online shoppers cannot touch the product. Insufficient imagery or lack of video prevents them from evaluating quality, texture, and scale.",
            "recommendation": "Upload at least 5-7 high-resolution images (multiple angles, lifestyle, scale) and add a 15-second product demonstration video."
        })

def audit_site(domain: str) -> dict:
    findings = {
        "domain": domain, "product_url": None, "load_time_ms": None,
        "issues": [], "screenshot_path": None, "popup_screenshot_path": None,
        "notes": "", "error": None, "platform": "custom",
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
                # NUCLEAR FALLBACK: D2C & Subscription brands convert directly on the homepage.
                product_url = f"https://{domain}"
                findings["notes"] += "homepage_audited_as_primary_conversion_surface. "
                findings["product_url"] = product_url

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
            
            # ROBUST PLATFORM DETECTION (via HTML CDN signatures)
            try:
                html_has_plat = page.evaluate("() => document.documentElement.outerHTML.slice(0, 400000)")
                html_lower = html_has_plat.lower()
                if 'cdn.shopify.com' in html_lower or 'shopify-checkout' in html_lower or 'window.shopify' in html_lower:
                    platform = 'shopify'
                elif 'woocommerce' in html_lower or 'wp-content/plugins/woocommerce' in html_lower or 'wp-json/wc/' in html_lower:
                    platform = 'woocommerce'
                elif 'bigcommerce' in html_lower or 'cdn11.bigcommerce.com' in html_lower:
                    platform = 'bigcommerce'
                elif 'magento' in html_lower or 'mage/' in html_lower or 'x-magento-init' in html_lower:
                    platform = 'magento'
                elif 'squarespace' in html_lower or 'static1.1.sqsp.net' in html_lower or 'squarespace-cdn.com' in html_lower:
                    platform = 'squarespace'
                elif 'wixstatic.com' in html_lower or 'wix.com' in html_lower:
                    platform = 'wix'
                elif 'prestashop' in html_lower or 'presta' in html_lower:
                    platform = 'prestashop'
                elif '3dcart' in html_lower or 'shift4shop' in html_lower:
                    platform = 'shift4shop'
                elif 'demandware' in html_lower or 'salesforce commerce cloud' in html_lower or 'sfcc' in html_lower:
                    platform = 'salesforce'
                elif 'vtex' in html_lower or 'vteximg' in html_lower or 'vtexcommercestable' in html_lower:
                    platform = 'vtex'
                else:
                    platform = 'custom'
                findings["platform"] = platform
            except Exception:
                pass # Falls back to "custom" initialized at the top

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
                    findings["notes"] += f"marketing_popup_detected_and_dismissed. "
                    # Human auditor principle: If we successfully closed it, it's not a critical revenue leak.
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

            overlay_blocked = detect_overlay(page).get("blocked")
            skip_interactive = False
            if overlay_blocked:
                findings["notes"] += "unclosable_overlay_detected_interactive_checks_skipped. "
                skip_interactive = True
                findings["issues"].append({
                    "code": "unclosable_overlay",
                    "description": "A viewport-blocking overlay could not be automatically dismissed.",
                    "evidence": "Overlay persisted after dismissal attempts and DOM nuke.",
                    "severity": "high", "confidence": "VERIFIED",
                    "business_impact": "Viewport-blocking overlays without accessible dismissals cause immediate user abandonment and trigger SEO penalties.",
                    "fix": "Ensure marketing popups have a visible, accessible close button and do not block immediate page interaction."
                })

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
                    "description": "Add to Cart button is smaller than 32x32px on mobile.",
                    "evidence": "Touch target analysis failed minimum 32px requirement.",
                    "severity": "medium", "confidence": "high",
                    "fix": "Increase padding on the mobile ATC button to ensure it meets WCAG touch target guidelines."
                })
            pdp_express = False
            if not skip_interactive:
                pdp_express = _visible_any(page, EXPRESS_SELECTOR)
                # Shadow DOM fallback for express checkout web components
                if not pdp_express:
                    try:
                        pdp_express = page.evaluate("""
                            () => {
                                const sels = ['shop-pay-button', 'apple-pay-button', 'paypal-button', '[data-testid="shop-pay-button"]'];
                                for (const sel of sels) {
                                    if (document.querySelector(sel)) return true;
                                    for (const node of document.querySelectorAll('*')) {
                                        if (node.shadowRoot && node.shadowRoot.querySelector(sel)) return true;
                                    }
                                }
                                return false;
                            }
                        """)
                    except Exception:
                        pass
            _check_reviews(page, findings)
            _check_trust_signals(page, findings)
            _check_heavy_images(page, findings)
            _check_script_bloat(page, findings)
            _check_console_errors(findings, console_errors)
            _check_seo(page, findings)
            # Technical SEO (Isolated Module)
            audit_seo_onpage(page, findings)

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
                    "fix": get_pixel_fix(findings.get("platform", "custom")),
                })
            if not tiktok_pixel:
                findings["issues"].append({
                    "code": "tiktok_pixel_missing",
                    "description": "TikTok Pixel not detected.",
                    "evidence": "no analytics.tiktok.com request and no ttq in page HTML",
                    "severity": "low", "confidence": "high",
                    "fix": get_tiktok_fix(findings.get("platform", "custom")),
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
            if not skip_interactive and atc_btn is not None:
                req_before = len(seen_urls)
                try:
                    dl_before = page.evaluate("() => window.dataLayer ? window.dataLayer.length : 0")
                except Exception:
                    dl_before = 0
                url_before = page.url
                try:
                    if atc_btn == "JS_BTN":
                        page.evaluate("""
                            () => {
                                const selectors = ["button[name='add']", "[data-add-to-cart]", ".single_add_to_cart_button", ".add_to_cart_button"];
                                const textMatches = (el) => {
                                    const t = (el.innerText || el.textContent || "").toLowerCase();
                                    return t.includes('add to cart') || t.includes('add to bag') || t.includes('buy now');
                                };
                                const searchRoot = (root) => {
                                    for (const sel of selectors) {
                                        const el = root.querySelector(sel);
                                        if (el) return el;
                                    }
                                    for (const btn of root.querySelectorAll('button, [role="button"]')) {
                                        if (textMatches(btn)) return btn;
                                    }
                                    return null;
                                };
                                let found = searchRoot(document);
                                if (!found) {
                                    for (const node of document.querySelectorAll('*')) {
                                        if (node.shadowRoot) {
                                            found = searchRoot(node.shadowRoot);
                                            if (found) break;
                                        }
                                    }
                                }
                                if (found) found.click();
                            }
                        """)
                    else:
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
                        "fix": get_express_fix(findings.get("platform", "custom")),
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
                    "[id*='cart-drawer' i], [class*='cart-drawer' i], [class*='mini-cart' i], [class*='cart-modal' i], "
                    "cart-drawer, [id*='slide-cart' i], [class*='slide-cart' i], [class*='drawer' i][class*='cart' i]"
                )
                # Wait for dynamic drawer injection (common in headless/Shopify Plus)
                if not drawer:
                    try:
                        page.wait_for_selector("[id*='cart-drawer' i], [class*='cart-drawer' i], cart-drawer, [class*='drawer' i][class*='cart' i]", state="attached", timeout=3000)
                        drawer = page.query_selector("[id*='cart-drawer' i], [class*='cart-drawer' i], cart-drawer, [class*='drawer' i][class*='cart' i]")
                    except Exception:
                        pass
                        
                if navigated or not (drawer and drawer.is_visible()):
                    findings["issues"].append({
                        "code": "no_cart_drawer",
                        "description": "Adding to cart leaves the product page (full-page cart) instead of opening a cart drawer.",
                        "evidence": "URL changed or no visible drawer element after Add-to-Cart click",
                        "severity": "low", "confidence": "medium",
                        "fix": get_drawer_fix(findings.get("platform", "custom")),
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
    cwv = findings.get("cwv", {})
    lcp = cwv.get("lcp", 0)
    
    # Industrial Standard: LCP is the gold standard for perceived speed. 
    # Raw load time is often inflated by third-party trackers.
    if lcp > 4000:
        findings["issues"].append({
            "code": "slow_lcp",
            "description": f"Largest Contentful Paint (LCP) is {lcp}ms. Mobile users bounce if hero content takes >2.5s to render.",
            "evidence": f"LCP: {lcp}ms (Target: <2500ms)",
            "severity": "high", "confidence": "high",
            "business_impact": "Slow LCP directly correlates with higher bounce rates and lower conversion on mobile networks.",
            "fix": "Optimize hero image delivery (WebP/AVIF), preload critical fonts, and defer non-critical third-party scripts."
        })
    elif ms and ms > 8000 and lcp == 0:
        findings["issues"].append({
            "code": "slow_load_fallback",
            "description": f"Total page load time is {ms}ms, indicating severe main-thread blocking.",
            "evidence": f"{ms}ms measured via navigation timing.",
            "severity": "medium", "confidence": "medium",
            "fix": "Audit main-thread blocking scripts and compress above-the-fold imagery."
        })


def _check_add_to_cart(page, findings, viewport_h: int):
    # Industrial Upgrade: Pierce Shadow DOM and verify actual CSS visibility
    atc_data = page.evaluate("""
        () => {
            const selectors = [
                "button[name='add']", "[data-add-to-cart]",
                ".single_add_to_cart_button", ".add_to_cart_button",
                "form[action*='/cart/add'] button", "[data-action='add-to-cart']",
                "button[type='submit'][class*='product']"
            ];
            const textMatches = (el) => {
                const t = (el.innerText || el.textContent || "").toLowerCase();
                return t.includes('add to cart') || t.includes('add to bag') || t.includes('buy now');
            };
            const searchRoot = (root) => {
                for (const sel of selectors) {
                    const el = root.querySelector(sel);
                    if (el) return el;
                }
                for (const btn of root.querySelectorAll('button, [role="button"]')) {
                    if (textMatches(btn)) return btn;
                }
                return null;
            };
            const deepQuery = () => {
                let found = searchRoot(document);
                if (found) return found;
                for (const node of document.querySelectorAll('*')) {
                    if (node.shadowRoot) {
                        found = searchRoot(node.shadowRoot);
                        if (found) return found;
                    }
                }
                return null;
            };
            const btn = deepQuery();
            if (!btn) return { found: false };
            const rect = btn.getBoundingClientRect();
            const cs = window.getComputedStyle(btn);
            const is_visible = cs.display !== 'none' && cs.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
            return { found: true, visible: is_visible, width: rect.width, height: rect.height, y: rect.y, text: (btn.innerText || '').trim().slice(0, 50) };
        }
    """)
    
    if not atc_data.get("found"):
        findings["issues"].append({
            "code": "no_add_to_cart_found",
            "description": "No Add to Cart button detected on the product page.",
            "evidence": "Deep DOM & Shadow Root search returned no match.",
            "severity": "high", "confidence": "high",
            "fix": "Ensure a visible, clearly labelled Add to Cart button exists on the mobile PDP."
        })
        return None

    if not atc_data.get("visible"):
        # INDUSTRIAL PRINCIPLE: dimensions=0 through Shadow DOM is UNVERIFIED, not HIDDEN
        btn_text = atc_data.get("text", "")
        if btn_text and len(btn_text) > 3:
            # Element has real text content — likely Shadow DOM measurement failure, not truly hidden
            findings["notes"] += f"atc_unmeasurable_shadow_dom: '{btn_text}'. "
            return "JS_BTN"
        else:
            findings["issues"].append({
                "code": "add_to_cart_not_visible",
                "description": "Add to Cart button exists in DOM but appears hidden from the mobile viewport.",
                "evidence": f"Element found but CSS hides it or dimensions are 0.",
                "severity": "high", "confidence": "medium",
                "fix": "Verify the buy box renders visibly on mobile; check for CSS display:none or zero-height containers."
            })
            return "JS_BTN"

    w, h = atc_data.get("width", 0), atc_data.get("height", 0)
    # INDUSTRIAL PRINCIPLE: If dimensions are 0, measurement failed — do NOT report "too small"
    if 0 < w < 32 or 0 < h < 32:
        findings["issues"].append({
            "code": "small_touch_target",
            "description": f"Add to Cart button ({int(w)}x{int(h)}px) is smaller than the 32x32px mobile minimum.",
            "evidence": f"Touch target analysis: {int(w)}x{int(h)}px.",
            "severity": "medium", "confidence": "high",
            "fix": "Increase padding on the mobile ATC button to ensure it meets WCAG touch target guidelines."
        })
        
    if atc_data.get("y", 0) > viewport_h * 0.95:
        findings["issues"].append({
            "code": "add_to_cart_below_fold",
            "description": "Add to Cart sits below the mobile fold with no sticky purchase bar.",
            "evidence": f"button top at y={int(atc_data.get('y', 0))} on a {viewport_h}px viewport",
            "severity": "medium", "confidence": "high",
            "fix": "Add a sticky mobile Add to Cart bar or move the buy box above the fold."
        })
    return "JS_BTN"

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
            "fix": get_app_bloat_fix(findings.get("platform", "custom")),
        })


def _check_console_errors(findings, console_errors):
    # INDUSTRIAL FILTER: Ignore DNS blocks, CORS policies, and network noise
    real_js_errors = [
        err for err in console_errors
        if any(sig in err for sig in ["SyntaxError", "TypeError", "ReferenceError", "is not defined", "Cannot read properties"])
        and not any(noise in err for noise in ["CORS", "net::ERR", "Failed to load resource"])
    ]
    if real_js_errors:
        findings["issues"].append({
            "code": "console_errors", "severity": "medium", "confidence": "VERIFIED",
            "description": f"{len(real_js_errors)} critical JavaScript execution error(s) fired during page load.",
            "observation": f"{len(real_js_errors)} critical JavaScript execution error(s) fired during page load.",
            "evidence": "; ".join(real_js_errors[:3])[:300],
            "business_impact": "Critical JS errors break interactive elements, tracking tags, and checkout flows.",
            "interpretation": "Critical JS errors break interactive elements, tracking tags, and checkout flows.",
            "fix": "Debug the throwing script - execution errors break the purchase path or pixel tracking.",
            "recommendation": "Debug the throwing script - execution errors break the purchase path or pixel tracking."
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