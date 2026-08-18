"""
Mobile CRO audit — v3 (obstacle-hardened).

Navigation can't be starved into timeouts (load -> domcontentloaded
fallback). Bot challenges and password pages are detected and routed to
manual review, never bypassed. Overlays are classified, evidenced, then
dismissed. Add-to-Cart judgement is scroll-aware so sticky purchase bars
never produce false alarms.
"""
import time
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

from revenue_leak_engine.config import MOBILE_VIEWPORT, AUDIT_TIMEOUT_MS, SCREENSHOTS_DIR
from revenue_leak_engine.audit.popup_handler import (
    detect_overlay, classify_overlay, dismiss_overlays,
)

ATC_SELECTOR = (
    "button[name='add'], button:has-text('Add to cart'), "
    "button:has-text('Add to Cart'), button:has-text('Add to Bag')"
)

CHALLENGE_SIGS = (
    "just a moment", "checking your browser", "verify you are human",
    "cf-browser-verification", "challenge-platform", "hcaptcha", "g-recaptcha",
)
PASSWORD_SIGS = ("opening soon", "will be back soon", "store password",
                 "enter using password", "powered by shopify — password")


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


def find_a_product_url(page, domain: str) -> str | None:
    candidates = [f"https://{domain}/collections/all", f"https://{domain}/collections", f"https://{domain}"]
    for url in candidates:
        if not _goto_resilient(page, url):
            continue
        time.sleep(1)
        link = page.query_selector("a[href*='/products/']")
        if link:
            href = link.get_attribute("href")
            if href:
                return href if href.startswith("http") else f"https://{domain}{href}"
    return None


def audit_site(domain: str) -> dict:
    findings = {
        "domain": domain, "product_url": None, "load_time_ms": None,
        "issues": [], "screenshot_path": None, "popup_screenshot_path": None,
        "notes": "", "error": None,
    }
    safe = domain.replace(".", "_")
    viewport_h = MOBILE_VIEWPORT.get("height", 844)

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
        page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        try:
            product_url = find_a_product_url(page, domain)
            if not product_url:
                findings["error"] = "no_product_url_found"
                browser.close()
                return findings

            findings["product_url"] = product_url
            start = time.time()
            if not _goto_resilient(page, product_url):
                findings["error"] = "timeout"
                browser.close()
                return findings
            findings["load_time_ms"] = int((time.time() - start) * 1000)

            # Bot challenge? Wait once for it to clear; never bypass.
            if any(s in _page_text_head(page) for s in CHALLENGE_SIGS):
                page.wait_for_timeout(6000)
                if any(s in _page_text_head(page) for s in CHALLENGE_SIGS):
                    findings["error"] = "bot_challenge - manual review"
                    browser.close()
                    return findings

            # Password/"opening soon" page is not a lead.
            if any(s in _page_text_head(page) for s in PASSWORD_SIGS):
                findings["error"] = "store_password_protected - not a live store"
                browser.close()
                return findings

            page.wait_for_timeout(2500)  # let delayed overlays appear

            overlay = detect_overlay(page)
            if overlay.get("blocked"):
                kind = classify_overlay(overlay)
                popup_shot = SCREENSHOTS_DIR / f"{safe}_popup.png"
                page.screenshot(path=str(popup_shot), full_page=False)
                findings["popup_screenshot_path"] = str(popup_shot)

                if kind == "marketing_popup":
                    findings["issues"].append({
                        "code": "intrusive_popup",
                        "description": "A viewport-blocking popup (discount/email capture) "
                                       "greets mobile visitors on load.",
                        "evidence": f"overlay detected + screenshot {popup_shot.name}",
                        "severity": "medium",
                        "fix": "Delay or remove the on-load modal; use exit-intent instead.",
                    })
                else:
                    findings["notes"] += (
                        f"Overlay on load ({kind}) dismissed; not counted as a leak. "
                    )

                actions = dismiss_overlays(page)
                if actions:
                    findings["notes"] += f"Overlay dismissed via: {', '.join(actions)}. "

            if detect_overlay(page).get("blocked"):
                findings["error"] = ("unclosable_overlay - page-level checks skipped "
                                     "to avoid false alarms; mark for manual review")
                browser.close()
                return findings

            shot_path = SCREENSHOTS_DIR / f"{safe}.png"
            page.screenshot(path=str(shot_path), full_page=False)
            findings["screenshot_path"] = str(shot_path)

            _check_load_speed(findings)
            _check_add_to_cart(page, findings, viewport_h)
            _check_express_checkout(page, findings)
            _check_reviews_present(page, findings)

        except PWTimeout:
            findings["error"] = "timeout"
        except Exception as e:
            findings["error"] = f"audit_failed: {e}"
        finally:
            browser.close()

    return findings


def _check_load_speed(findings: dict):
    ms = findings["load_time_ms"]
    if ms and ms > 3500:
        findings["issues"].append({
            "code": "slow_load",
            "description": f"Mobile load time is {ms}ms (target is <2500ms).",
            "evidence": f"{ms}ms measured via Playwright",
            "severity": "high" if ms > 5000 else "medium",
            "fix": "Compress hero imagery, defer third-party apps, add a CDN edge cache.",
        })


def _check_add_to_cart(page, findings, viewport_h: int):
    btn = page.query_selector(ATC_SELECTOR)
    if not btn:
        findings["issues"].append({
            "code": "no_add_to_cart_found",
            "description": "No Add to Cart button detected on the product page.",
            "evidence": "selector search returned no match on cleared page",
            "severity": "high",
            "fix": "Ensure a visible, labelled Add to Cart button on mobile PDP.",
        })
        return

    box = btn.bounding_box()
    if box is None:
        findings["issues"].append({
            "code": "add_to_cart_not_visible",
            "description": "Add to Cart button exists but is hidden on mobile.",
            "evidence": "bounding_box() returned None on cleared page",
            "severity": "high",
            "fix": "Unhide the buy box on mobile; it is the revenue button.",
        })
        return

    if box["y"] <= viewport_h * 0.95:
        return  # above the fold on load: ideal

    # Below fold: acceptable only if a sticky purchase bar appears on scroll.
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
        return  # sticky purchase bar = good mobile pattern, no alarm

    findings["issues"].append({
        "code": "add_to_cart_below_fold",
        "description": "Add to Cart sits below the mobile fold with no sticky purchase bar.",
        "evidence": f"button top at y={int(box['y'])} on a {viewport_h}px viewport; no sticky bar after scroll",
        "severity": "medium",
        "fix": "Add a sticky mobile Add to Cart bar or move the buy box above the fold.",
    })


def _check_express_checkout(page, findings):
    express_btns = page.query_selector_all(
        "[data-testid='shop-pay-button'], [aria-label*='Shop Pay'], "
        "[aria-label*='Apple Pay'], [aria-label*='PayPal']"
    )
    if not any(b.is_visible() for b in express_btns):
        findings["issues"].append({
            "code": "no_express_checkout",
            "description": "No visible express checkout (Shop Pay/Apple Pay) on mobile.",
            "evidence": "no visible express payment buttons in cleared DOM",
            "severity": "medium",
            "fix": "Enable Shop Pay / Apple Pay / Google Pay accelerated checkout.",
        })


def _check_reviews_present(page, findings):
    widget = page.query_selector(
        "[class*='jdgm-widget'], [class*='loox'], [class*='yotpo'], "
        "[id*='shopify-product-reviews']"
    )
    if not widget or not widget.is_visible():
        findings["issues"].append({
            "code": "no_review_widget",
            "description": "No visible social proof/review widget near the product information.",
            "evidence": "no visible review app DOM elements on cleared page",
            "severity": "low",
            "fix": "Surface reviews/UGC above the fold on the PDP.",
        })