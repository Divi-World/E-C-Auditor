"""
Pulls brands currently running Meta ads for a set of niche keywords, using
the public Ad Library API (ads_archive endpoint). Ad-running = budget +
belief in growth, which makes this a much stronger qualifier than guessing
from follower counts or product listings.

Docs: https://www.facebook.com/ads/library/api/

Note: the Ad Library API does not return a clean landing-page-url field for
commercial ads. We fetch each ad's public snapshot page and resolve the
real landing domain from og:url/canonical tags, CTA-labeled links, or any
outbound link — in that priority order — unwrapping Meta's l.php redirect
wrapper along the way. It's a scrape of a public page Meta itself serves
for transparency, so keep volume low and respectful (RATE_LIMIT_SECS).
"""
import re
import time
import httpx
from urllib.parse import urlparse, parse_qs, unquote
from bs4 import BeautifulSoup

from revenue_leak_engine.config import META_ACCESS_TOKEN, META_AD_LIBRARY_URL

RATE_LIMIT_SECS = 1.5
MAX_RETRIES = 2

# Domains that are never the real landing page — social platforms, link
# shorteners, and tracking redirectors. Extend as you find more false
# positives during manual review.
IGNORED_DOMAINS = {
    "facebook.com", "instagram.com", "fb.com", "l.facebook.com", "meta.com",
    "lm.facebook.com", "m.facebook.com", "fb.watch",
    "bit.ly", "tinyurl.com", "linktr.ee", "l.instagram.com",
    "youtube.com", "youtu.be", "tiktok.com",
}

# Two-part public suffixes handled when computing the "root" domain, so
# https://shop.brand.co.uk and https://brand.co.uk are treated as one lead.
# Not exhaustive — extend as you expand past the US.
MULTI_PART_TLDS = {"co.uk", "com.au", "co.nz", "co.za"}


def search_active_ads(search_term: str, country: str = "US", limit: int = 25) -> list[dict]:
    """Query Ad Library for active ads matching a search term. Returns raw ad dicts."""
    if not META_ACCESS_TOKEN:
        raise RuntimeError(
            "META_ACCESS_TOKEN not set. Create a Meta developer app and add a "
            "token to .env — see .env.example."
        )

    params = {
        "access_token": META_ACCESS_TOKEN,
        "search_terms": search_term,
        "ad_type": "ALL",
        "ad_active_status": "ACTIVE",
        "ad_reached_countries": f"['{country}']",
        "fields": "page_name,ad_snapshot_url,ad_delivery_start_time",
        "limit": min(limit, 100),
    }

    with httpx.Client(timeout=15) as client:
        resp = client.get(META_AD_LIBRARY_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    return data.get("data", [])


def _root_domain(domain: str) -> str:
    """Collapse subdomains: shop.brand.com -> brand.com, brand.co.uk stays as-is."""
    parts = domain.lower().split(".")
    if len(parts) <= 2:
        return domain.lower()
    last_two = ".".join(parts[-2:])
    if last_two in MULTI_PART_TLDS and len(parts) >= 3:
        return ".".join(parts[-3:])
    return last_two


def _unwrap_facebook_redirect(url: str) -> str:
    """Meta often wraps outbound links as l.facebook.com/l.php?u=<real_url>."""
    parsed = urlparse(url)
    if "facebook.com" in parsed.netloc and parsed.path in ("/l.php", "/l/"):
        qs = parse_qs(parsed.query)
        real = qs.get("u", [None])[0]
        if real:
            return unquote(real)
    return url


def _extract_candidate_links(html: str) -> list[str]:
    """
    Candidate outbound URLs in priority order:
      1. og:url / canonical meta tags (most reliable when present)
      2. CTA-style links (Shop Now / Learn More / Visit page text)
      3. any remaining <a href>
    """
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[str] = []

    for tag_name, attr in (("meta", "og:url"), ("link", "canonical")):
        tag = soup.find(tag_name, attrs={"property": attr}) or soup.find(tag_name, rel=attr)
        if tag:
            val = tag.get("content") or tag.get("href")
            if val:
                candidates.append(val)

    cta_words = ("shop now", "learn more", "visit", "shop", "order now", "get offer")
    for a in soup.find_all("a", href=True):
        text = (a.get_text() or "").strip().lower()
        if any(w in text for w in cta_words):
            candidates.append(a["href"])

    for a in soup.find_all("a", href=True):
        candidates.append(a["href"])

    return candidates


def extract_landing_domain(ad_snapshot_url: str) -> str | None:
    """
    Fetch an ad's public snapshot page and resolve the real landing domain.
    Retries transient failures before giving up — a lead silently dropped
    here is a lead you never see, so we retry rather than skip.
    """
    for attempt in range(MAX_RETRIES + 1):
        try:
            with httpx.Client(timeout=15, follow_redirects=True) as client:
                resp = client.get(ad_snapshot_url, headers={"User-Agent": "Mozilla/5.0"})
                resp.raise_for_status()
            break
        except httpx.HTTPError:
            if attempt < MAX_RETRIES:
                time.sleep(1.0)
    else:
        return None  # exhausted retries

    for raw_url in _extract_candidate_links(resp.text):
        url = _unwrap_facebook_redirect(raw_url)
        match = re.search(r"https?://([^/?#]+)", url)
        if not match:
            continue
        domain = match.group(1).replace("www.", "")
        if any(ignored in domain for ignored in IGNORED_DOMAINS):
            continue
        return _root_domain(domain)

    return None


def find_advertiser_domains(keywords: list[str], country: str = "US", per_keyword: int = 15) -> list[dict]:
    """
    Runs search_active_ads for each keyword, resolves landing domains, and
    returns deduped candidates: [{page_name, domain, ad_snapshot_url, matched_keyword}, ...]
    """
    seen_domains = set()
    results = []

    for term in keywords:
        ads = search_active_ads(term, country=country, limit=per_keyword)
        for ad in ads:
            snapshot_url = ad.get("ad_snapshot_url")
            page_name = ad.get("page_name", "unknown")
            if not snapshot_url:
                continue

            time.sleep(RATE_LIMIT_SECS)
            domain = extract_landing_domain(snapshot_url)
            if not domain or domain in seen_domains:
                continue

            seen_domains.add(domain)
            results.append({
                "page_name": page_name,
                "domain": domain,
                "ad_snapshot_url": snapshot_url,
                "matched_keyword": term,
            })

    return results
