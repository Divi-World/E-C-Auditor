"""
Self-aware obstacle handling — v3.

v2 blind spots fixed:
  - Bottom-sheet consent banners never cover the viewport centre, so a
    single centre probe missed them. Now we probe 5 points and also
    match consent/region/age signatures.
  - Dismissal vocabulary now includes real-world consent buttons
    ("Ok - that's fine", "No", "Agree", ...), region gates and age gates.

Integrity rules unchanged: marketing popups are recorded WITH screenshot
evidence BEFORE dismissal; surgical DOM removal is a last resort and only
clears the view — it never hides a finding. CAPTCHAs are never solved.
"""
import re

# Probe 5 viewport points; return the largest fixed/absolute overlay.
OVERLAY_DETECT_JS = """
() => {
    const probes = [[0.5,0.5],[0.5,0.85],[0.5,0.2],[0.15,0.5],[0.85,0.5]];
    const seen = new Set();
    let best = null;
    for (const [fx, fy] of probes) {
        const el = document.elementFromPoint(innerWidth * fx, innerHeight * fy);
        if (!el) continue;
        let node = el;
        while (node && node !== document.documentElement) {
            if (seen.has(node)) break;
            const cs = getComputedStyle(node);
            const r = node.getBoundingClientRect();
            const hidden = cs.display === 'none' || cs.visibility === 'hidden' ||
                           parseFloat(cs.opacity || '1') === 0;
            const fixedish = cs.position === 'fixed' || cs.position === 'absolute';
            const big = r.width >= innerWidth * 0.5 && r.height >= innerHeight * 0.25;
            if (!hidden && fixedish && big) {
                seen.add(node);
                const area = r.width * r.height;
                if (!best || area > best.area) best = { node, area };
                break;
            }
            node = node.parentElement;
        }
    }
    if (!best) return { blocked: false };
    const n = best.node;
    return {
        blocked: true,
        tag: n.tagName || '',
        src: n.src || '',
        id: n.id || '',
        cls: String(n.className || '').slice(0, 140),
        text: (n.innerText || '').replace(/\\s+/g, ' ').slice(0, 300)
    };
}
"""

REMOVE_OVERLAY_JS = """
() => {
    const x = innerWidth / 2, y = innerHeight / 2;
    const el = document.elementFromPoint(x, y);
    if (!el) return false;
    let node = el, target = null;
    while (node && node !== document.documentElement) {
        const cs = getComputedStyle(node);
        const r = node.getBoundingClientRect();
        if (r.width >= innerWidth * 0.5 && r.height >= innerHeight * 0.25 &&
            (cs.position === 'fixed' || cs.position === 'absolute')) { target = node; break; }
        node = node.parentElement;
    }
    if (!target) return false;
    target.remove();
    document.querySelectorAll('div, section').forEach(n => {
        const cs = getComputedStyle(n);
        const r = n.getBoundingClientRect();
        if (cs.position === 'fixed' && r.width >= innerWidth * 0.9 &&
            r.height >= innerHeight * 0.9) n.remove();
    });
    return true;
}
"""

UNLOCK_SCROLL_JS = """
() => {
    document.documentElement.style.overflow = '';
    document.body.style.overflow = '';
    document.body.classList.remove('noscroll', 'no-scroll', 'overflow-hidden',
        'modal-open', 'popup-open', 'klaviyo-form-open', 'fancybox-lock');
    return true;
}
"""

COOKIE_RE = re.compile(r"\b(cookies?|privacy|consent|gdpr|ccpa)\b", re.I)
MARKETING_RE = re.compile(r"(%\s*off|unlock|discount|subscribe|sign\s*up|join|"
                          r"early access|shopping for|get\s*\d+)", re.I)
APP_SIG_RE = re.compile(r"(klaviyo|privy|justuno|popup|modal|newsletter)", re.I)
AGE_RE = re.compile(r"(are you \d{2}\+?|over \d{2}|age verif|born in)", re.I)
REGION_RE = re.compile(r"(choose your (country|region)|select (your )?(country|region)|"
                       r"shipping to|ship to)", re.I)

CLOSE_SELECTORS = [
    '[role="dialog"] [aria-label*="close" i]',
    '[aria-label*="close" i]',
    '[aria-label*="dismiss" i]',
    '.klaviyo-form-close',
    '[class*="klaviyo"] [class*="close" i]',
    'button[class*="close" i]',
    'a[class*="close" i]',
    'div[role="button"][class*="close" i]',
    'span[class*="close" i]',
    '[class*="dismiss" i]',
    'button:has-text("×")',
    'button:has-text("✕")',
    'a:has-text("×")',
    'div[role="button"]:has-text("×")',
    'button:has-text("Close")',
    'button:has-text("No thanks")',
    'button:has-text("No, thanks")',
    'button:has-text("No thank you")',
    'button:has-text("Maybe later")',
    'button:has-text("Not now")',
    'button:has-text("Continue without discount")',
    'button:has-text("Decline")',
]

COOKIE_SELECTORS = [
    "button:has-text(\"that's fine\")",
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
]

REGION_SELECTORS = [
    'button:has-text("United States")',
    'a:has-text("United States")',
    'button:text-is("US")',
    'a:text-is("US")',
    'button:has-text("Canada")',
    'a:has-text("Canada")',
    'button:has-text("United Kingdom")',
    'a:has-text("United Kingdom")',
]

AGE_SELECTORS = [
    'button:has-text("Yes, I am")',
    'button:has-text("I am 21")',
    'button:has-text("I am 18")',
    "button:has-text(\"I'm over 21\")",
    "button:has-text(\"I'm over 18\")",
    'button:has-text("Enter site")',
]


def detect_overlay(page) -> dict:
    try:
        return page.evaluate(OVERLAY_DETECT_JS) or {"blocked": False}
    except Exception:
        return {"blocked": False}


def classify_overlay(info: dict) -> str:
    """cookie_consent | age_gate | region_gate | marketing_popup | generic_overlay"""
    text = info.get("text", "")
    blob = f"{info.get('id', '')} {info.get('cls', '')} {info.get('src', '')} {text}"
    if COOKIE_RE.search(blob) and not MARKETING_RE.search(text):
        return "cookie_consent"
    if AGE_RE.search(text):
        return "age_gate"
    if REGION_RE.search(text):
        return "region_gate"
    if MARKETING_RE.search(text) or APP_SIG_RE.search(blob):
        return "marketing_popup"
    return "generic_overlay"


def _try_click(frame, selectors) -> str | None:
    for sel in selectors:
        try:
            loc = frame.locator(sel).first
            if loc.count() > 0 and loc.is_visible():
                loc.click(timeout=1200)
                return sel
        except Exception:
            continue
    return None


def _dismiss_once(page, info: dict) -> str | None:
    frame = page.main_frame
    if info.get("tag", "").upper() == "IFRAME":
        src = (info.get("src") or "").split("?")[0]
        for fr in page.frames:
            if fr is not page.main_frame and src and fr.url.split("?")[0] == src:
                frame = fr
                break
        else:
            frame = page.frames[1] if len(page.frames) > 1 else page.main_frame

    kind = classify_overlay(info)

    if kind == "region_gate":
        acted = _try_click(frame, REGION_SELECTORS)
        if acted:
            return f"region:{acted}"
    if kind == "age_gate":
        acted = _try_click(frame, AGE_SELECTORS)
        if acted:
            return f"age:{acted}"

    acted = _try_click(frame, CLOSE_SELECTORS)
    if acted:
        return f"close:{acted}"

    if kind == "cookie_consent":
        acted = _try_click(frame, COOKIE_SELECTORS)
        if acted:
            return f"cookie:{acted}"

    if info.get("tag", "").upper() != "IFRAME":
        try:
            page.mouse.click(8, page.viewport_size["height"] // 2)
            page.wait_for_timeout(600)
            if not detect_overlay(page).get("blocked"):
                return "backdrop_click"
        except Exception:
            pass

    try:
        page.keyboard.press("Escape")
        page.wait_for_timeout(600)
        if not detect_overlay(page).get("blocked"):
            return "escape"
    except Exception:
        pass

    # Last resort: surgical removal (evidence already banked by caller).
    try:
        if frame is not page.main_frame:
            frame.evaluate(REMOVE_OVERLAY_JS)
        page.evaluate(REMOVE_OVERLAY_JS)
        return "js_remove_overlay"
    except Exception:
        return None


def dismiss_overlays(page, max_rounds: int = 5) -> list[str]:
    actions = []
    for _ in range(max_rounds):
        info = detect_overlay(page)
        if not info.get("blocked"):
            break
        acted = _dismiss_once(page, info)
        if not acted:
            break
        actions.append(acted)
        page.wait_for_timeout(700)
    for fr in page.frames:
        try:
            fr.evaluate(UNLOCK_SCROLL_JS)
        except Exception:
            continue
    return actions