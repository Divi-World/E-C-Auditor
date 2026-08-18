"""
Confirms whether a domain is a Shopify store, with a confidence score based
on how many independent signals agree. Cheap, no paid API needed.
"""
import httpx

SIGNALS = {
    "cdn_shopify": "cdn.shopify.com",
    "shopify_theme_js": "Shopify.theme",
    "shopify_routes": "Shopify.routes",
    "myshopify_meta": "myshopify.com",
}


def normalize_domain(domain: str) -> str:
    domain = domain.strip().lower()
    domain = domain.replace("https://", "").replace("http://", "").rstrip("/")
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def check_cart_endpoint(domain: str) -> bool:
    """Shopify stores expose a predictable /cart.js JSON endpoint."""
    try:
        with httpx.Client(timeout=10, follow_redirects=True) as client:
            resp = client.get(f"https://{domain}/cart.js", headers={"User-Agent": "Mozilla/5.0"})
        return resp.status_code == 200 and "token" in resp.text.lower()
    except httpx.HTTPError:
        return False


def is_shopify(domain: str) -> dict:
    """
    Returns {domain, is_shopify: bool, confidence: 0-1, signals_found: [...]}
    confidence >= 0.5 (2+ signals, or the cart endpoint alone) is safe to
    treat as confirmed.
    """
    domain = normalize_domain(domain)
    signals_found = []

    try:
        with httpx.Client(timeout=10, follow_redirects=True) as client:
            resp = client.get(f"https://{domain}", headers={"User-Agent": "Mozilla/5.0"})
        html = resp.text
    except httpx.HTTPError:
        return {"domain": domain, "is_shopify": False, "confidence": 0.0,
                "signals_found": [], "error": "unreachable"}

    for name, needle in SIGNALS.items():
        if needle.lower() in html.lower():
            signals_found.append(name)

    if check_cart_endpoint(domain):
        signals_found.append("cart_js_endpoint")

    confidence = min(len(signals_found) / 2, 1.0)
    return {
        "domain": domain,
        "is_shopify": confidence >= 0.5,
        "confidence": confidence,
        "signals_found": signals_found,
    }
