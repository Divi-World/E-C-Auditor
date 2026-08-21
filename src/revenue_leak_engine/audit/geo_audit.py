import re
from revenue_leak_engine.audit.copy_bank import ISSUE_COPY
import json
import xml.etree.ElementTree as ET
import requests as std_requests
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup

try:
    from curl_cffi import requests as cffi_requests
    USE_STEALTH = True
except ImportError:
    USE_STEALTH = False

import sqlite3, hashlib, time, os
CACHE_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'data', 'http_cache.db')
os.makedirs(os.path.dirname(CACHE_DB), exist_ok=True)

def _init_cache():
    try:
        conn = sqlite3.connect(CACHE_DB)
        conn.execute("CREATE TABLE IF NOT EXISTS http_cache (url_hash TEXT PRIMARY KEY, status INTEGER, text TEXT, final_url TEXT, headers TEXT, timestamp REAL)")
        conn.commit()
        conn.close()
    except Exception: pass
_init_cache()

class MockResp:
    def __init__(self, status, text, url, headers_str):
        self.status_code = status
        self.text = text or ""
        self.url = url
        self.headers = headers_str
        self.content = self.text.encode("utf-8", errors="ignore")

_orig_cffi_get = cffi_requests.get if USE_STEALTH else None
_orig_std_get = std_requests.get

def _cached_get(url, **kwargs):
    url_hash = hashlib.md5(url.encode("utf-8")).hexdigest()
    try:
        conn = sqlite3.connect(CACHE_DB)
        c = conn.cursor()
        c.execute("SELECT status, text, final_url, headers, timestamp FROM http_cache WHERE url_hash=?", (url_hash,))
        row = c.fetchone()
        conn.close()
        if row and (time.time() - row[4]) < 43200: # 12 hour cache
            return MockResp(row[0], row[1], row[2], row[3])
    except Exception: pass
    
    r = _orig_cffi_get(url, **kwargs) if (USE_STEALTH and _orig_cffi_get) else _orig_std_get(url, **kwargs)
    
    try:
        conn = sqlite3.connect(CACHE_DB)
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO http_cache VALUES (?,?,?,?,?,?)",
                  (url_hash, r.status_code, r.text, str(r.url), str(r.headers), time.time()))
        conn.commit()
        conn.close()
    except Exception: pass
    return r

if USE_STEALTH: cffi_requests.get = _cached_get
std_requests.get = _cached_get

TIMEOUT = 10
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; RevenueLeakEngine/7.0-Enterprise)"}

WEIGHTS = {
    "crawlability": 0.20,
    "entity_intelligence": 0.25,
    "product_intelligence": 0.30,
    "answerability": 0.15,
    "agentic_commerce": 0.10
}

PLATFORM_PATTERNS = {
    "shopify": {"product": "/products/", "collection": "/collections/", "exclude": "/collections/"},
    "woocommerce": {"product": "/product/", "collection": "/product-category/", "exclude": "/product-category/"},
    "unknown": {"product": "/product", "collection": "/category", "exclude": "/category"}
}

# Enterprise Reality: Strict Product URL Blacklist
_PRODUCT_BLACKLIST = ['gift-card', 'gift_card', '/search', '/policies/', '/cart', '/checkout', '/blogs/', '/account', '/login', '/register', '/password', '/contact-us', '/faq']

def _is_valid_product_url(url):
    url_lower = url.lower()
    if any(bl in url_lower for bl in _PRODUCT_BLACKLIST):
        return False
    return True

def _ensure_primary_domain(url_str, primary_domain):
    try:
        parsed = urlparse(url_str)
        if parsed.netloc != primary_domain and primary_domain in parsed.netloc:
            return parsed._replace(netloc=primary_domain).geturl()
        return url_str
    except Exception:
        return url_str

import random
_BROWSERS = ["chrome120", "chrome110", "safari15_5", "edge101"]

def _fetch(url, notes_key, findings):
    try:
        if USE_STEALTH:
            # Industrial WAF Bypass: Rotate TLS fingerprints on every request
            browser = random.choice(_BROWSERS)
            r = cffi_requests.get(url, timeout=TIMEOUT, impersonate=browser, allow_redirects=True)
        else:
            r = requests.get(url, timeout=TIMEOUT, headers=HEADERS, allow_redirects=True)
        return r.status_code, r.text, str(r.url), r.headers
    except Exception as e:
        findings["notes"] += f"{notes_key}: {type(e).__name__}. "
        return None, "", "", {}

def _fetch_with_retry(url, notes_key, findings, retries=1, base_timeout=TIMEOUT):
    timeouts = [base_timeout, base_timeout + 10]
    for idx, tout in enumerate(timeouts[:retries+1]):
        try:
            if USE_STEALTH:
                r = cffi_requests.get(url, timeout=tout, impersonate="chrome120", allow_redirects=True)
            else:
                r = requests.get(url, timeout=tout, headers=HEADERS, allow_redirects=True)
            return r.status_code, r.text, str(r.url), r.headers
        except Exception as e:
            findings["notes"] += f"{notes_key} attempt {idx+1} ({tout}s): {type(e).__name__}. "
            if idx == retries:
                return None, "", "", {}
    return None, "", "", {}

def _looks_blocked(text):
    if not text: return False
    lower_text = text.lower()
    if "just a moment..." in lower_text: return True
    if "window._cf_chl_opt" in lower_text: return True
    if "cloudflare" in lower_text and "challenge" in lower_text: return True
    if "captcha" in lower_text: return True
    return False

def _is_soft_404(text, ct):
    if not text: return True
    try:
        # Bulletproof extraction: handles strings, dicts, and curl_cffi Headers objects
        if hasattr(ct, 'get'):
            ct_str = str(ct.get('content-type', '') or ct.get('Content-Type', ''))
        else:
            ct_str = str(ct or "")
        if "text/html" in ct_str.lower(): return True
    except Exception:
        pass
        
    lower_text = text[:500].lower()
    if "<!doctype html" in lower_text or "<html" in lower_text: return True
    return False

def _extract_json_ld(html):
    if not html: return []
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    scripts = soup.find_all('script', type='application/ld+json')
    nodes = []
    for s in scripts:
        raw = s.string
        if not raw: continue
        try:
            clean = raw.replace('&quot;', '"').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
            clean = re.sub(r',(\s*[}\]])', r'\1', clean)
            clean = re.sub(r'//.*', '', clean)
            data = json.loads(clean)
            if isinstance(data, list): nodes.extend(data)
            else: nodes.append(data)
        except Exception:
            type_match = re.search(r'"@type"\s*:\s*"?([A-Za-z,\s]+)"?', raw)
            if type_match:
                nodes.append({"@type": type_match.group(1).strip(), "_fallback": True})
    
    # Canonical Flatten: Ensure @graph and nested arrays are fully expanded
    flat_nodes = []
    for n in nodes:
        if isinstance(n, dict):
            if "@graph" in n:
                flat_nodes.extend([g for g in n["@graph"] if isinstance(g, dict)])
            else:
                flat_nodes.append(n)
        elif isinstance(n, list):
            flat_nodes.extend([g for g in n if isinstance(g, dict)])
    
    # Normalize AggregateOffer to standard Offer structure for downstream consistency
    for n in flat_nodes:
        if "Product" in str(n.get("@type", "")):
            offers = n.get("offers")
            if isinstance(offers, dict) and offers.get("@type") == "AggregateOffer":
                if "lowPrice" in offers and "price" not in offers:
                    offers["price"] = offers["lowPrice"]
                if "highPrice" in offers and "price" not in offers:
                    offers["price"] = offers["highPrice"]
    return flat_nodes


def _extract_links(html, base_url):
    soup = BeautifulSoup(html, 'html.parser')
    links = []
    for a in soup.find_all('a', href=True):
        links.append(urljoin(base_url, a['href']))
    return links

def _detect_platform(html, headers):
    headers = headers or {}
    html_lower = (html or "").lower()
    headers_str = str(headers).lower()
    
    # TIER 1: DEFINITIVE CDNs (Must be checked first to avoid text-based false positives)
    if any(sig in html_lower or sig in headers_str for sig in ["cdn.shopify.com", "shopify.com", "myshopify.com", "x-shopid", "shopify-section", "shopify.pay", "shopify-checkout"]): return "shopify"
    if "bigcommerce.com" in html_lower or "cdn11.bigcommerce.com" in html_lower or "bc-ray" in headers_str: return "bigcommerce"
    if "squarespace-cdn.com" in html_lower or "squarespace" in html_lower: return "squarespace"
    if "wixstatic.com" in html_lower or "wix.com" in html_lower: return "wix"
    
    # TIER 2: ENTERPRISE PLATFORMS (Strict JS/Header signatures)
    if any(sig in html_lower or sig in headers_str for sig in ["demandware", "dw.__version__", "salesforce commerce cloud", "sfcc"]): return "salesforce"
    if any(sig in html_lower or sig in headers_str for sig in ["vtex", "vtexcommercestable", "vtex.local", "vteximg"]): return "vtex"
    if any(sig in html_lower or sig in headers_str for sig in ["x-magento-init", "mage/cookies", "mage/"]): return "magento"
    if "next" in headers_str or "__next" in html_lower or "_next/static" in html_lower: return "custom_headless"
    
    # TIER 3: STRICT CMS (Avoid generic text mentions)
    if any(sig in html_lower for sig in ["/wp-content/plugins/woocommerce/", "wc-block", "woocommerce-json-ld"]): return "woocommerce"
    if any(sig in html_lower for sig in ["/wp-content/themes/", "/wp-includes/", "wp-emoji-release.min.js"]): return "wordpress"
        
    return 'unknown'




def _sanitize_product_name(name, domain, brand):
    if not name: return "REPLACE_WITH_PRODUCT_NAME"
    n_low = name.lower().strip().replace("www.", "")
    d_low = domain.lower().strip().replace("www.", "")
    b_low = brand.lower().strip() if brand else ""
    if n_low == d_low or n_low == b_low or n_low in ["sample product", "premium product", "home", "cart", "shop", ""]:
        return "REPLACE_WITH_PRODUCT_NAME"
    return name
def _generate_snippet(code_type, domain, sample_name=""):
    if code_type == "organization":
        return '<script type="application/ld+json">\n{\n  "@context": "https://schema.org",\n  "@type": "Organization",\n  "name": "REPLACE_WITH_BRAND_NAME",\n  "url": "https://' + domain + '",\n  "logo": "REPLACE_WITH_LOGO_URL",\n  "sameAs": [ "REPLACE_WITH_SOCIAL_URLS" ]\n}\n</script>'
    elif code_type == "faq":
        return '<script type="application/ld+json">\n{\n  "@context": "https://schema.org",\n  "@type": "FAQPage",\n  "mainEntity": [{\n    "@type": "Question",\n    "name": "REPLACE_WITH_QUESTION",\n    "acceptedAnswer": {\n      "@type": "Answer",\n      "text": "REPLACE_WITH_ANSWER"\n    }\n  }]\n}\n</script>'
    elif code_type == "breadcrumb":
        return '<script type="application/ld+json">\n{\n  "@context": "https://schema.org",\n  "@type": "BreadcrumbList",\n  "itemListElement": [{\n    "@type": "ListItem",\n    "position": 1,\n    "name": "Home",\n    "item": "https://' + domain + '"\n  }]\n}\n</script>'
    elif code_type == "product":
        return '<script type="application/ld+json">\n{\n  "@context": "https://schema.org",\n  "@type": "Product",\n  "name": "' + (sample_name if sample_name and sample_name != domain else 'REPLACE_WITH_PRODUCT_NAME') + '",\n  "image": "REPLACE_WITH_IMAGE_URL",\n  "description": "REPLACE_WITH_DESCRIPTION",\n  "sku": "NOT_DETECTED",\n  "offers": {\n    "@type": "Offer",\n    "url": "https://' + domain + '/REPLACE_WITH_PRODUCT_URL",\n    "priceCurrency": "USD",\n    "price": "NOT_DETECTED",\n    "availability": "https://schema.org/InStock"\n  }\n}\n</script>'
    return ""


def _check_domain_reachable(domain: str, findings: dict) -> bool:
    st, _, _, _ = _fetch(f"https://{domain}/", "reachability_check", findings)
    if st is None:
        findings["notes"] += "Domain unreachable (DNS/connection failure) - audit aborted. "
        return False
    return True

def _is_policy_link(url: str) -> bool:
    path = urlparse(url).path.lower()
    return any(p in path for p in ["/shipping", "/return", "/refund", "/faq", "/contact"])

def _sample_urls(domain, findings):
    urls = {"homepage": f"https://{domain}/"}
    # Try default sitemap first
    # Try main sitemap, then enterprise index sitemaps
    status, xml, final_url, _ = _fetch_with_retry(f"https://{domain}/sitemap.xml", "sitemap", findings, retries=1)
    if status in [404, None]:
        status, xml, final_url, _ = _fetch_with_retry(f"https://{domain}/sitemap_index.xml", "sitemap_index", findings, retries=0)
    
    # WAF BYPASS: If default sitemap is blocked (403/429) or missing (404), check robots.txt for alternate sitemaps
    if status in [403, 404, 429, None]:
        robots_st, robots_txt, _, _ = _fetch_with_retry(f"https://{domain}/robots.txt", "robots_fallback", findings, retries=0)
        if robots_st == 200 and robots_txt:
            sitemap_urls = re.findall(r'(?i)Sitemap:\s*(https?://[^\s]+)', robots_txt)
            for alt_sitemap in sitemap_urls[:3]: # Try up to 3 alternate sitemaps
                if "product" in alt_sitemap.lower() or "sitemap" in alt_sitemap.lower():
                    alt_st, alt_xml, _, _ = _fetch_with_retry(alt_sitemap, "sitemap_alt", findings, retries=0)
                    if alt_st == 200 and alt_xml and ("<urlset" in alt_xml or "<sitemapindex" in alt_xml):
                        status, xml, final_url = alt_st, alt_xml, alt_sitemap
                        findings["notes"] += f"fallback_sitemap_used: {alt_sitemap}. "
                        break
    
    if status != 200:
        findings["notes"] += f"sitemap_fetch_failed: status={status} url={final_url}. "
    elif not xml or len(xml.strip()) == 0:
        findings["notes"] += "sitemap_empty_response. "

    products, collections, policies = [], [], []

    def parse_locs(xml_text):
        clean_xml = re.sub(r'\sxmlns(:[a-zA-Z0-9]+)?="[^"]+"', '', xml_text)
        clean_xml = re.sub(r'([<\/])[a-zA-Z0-9]+:', r'\1', clean_xml)
        try:
            root = ET.fromstring(clean_xml)
            return [loc.text for loc in root.findall('.//loc') if loc.text]
        except ET.ParseError:
            # Fallback to bulletproof regex if XML is malformed
            return re.findall(r'<loc>(.*?)</loc>', clean_xml, re.IGNORECASE | re.DOTALL)

    if status == 200 and xml:
        # BULLETPROOF GZIP FIX: If text is garbage, fetch raw bytes and decompress
        if not xml.strip().startswith('<?xml') and not xml.strip().startswith('<'):
            try:
                if USE_STEALTH:
                    raw_r = cffi_requests.get(final_url or f"https://{domain}/sitemap.xml", timeout=TIMEOUT, impersonate="chrome120", allow_redirects=True)
                else:
                    raw_r = requests.get(final_url or f"https://{domain}/sitemap.xml", timeout=TIMEOUT, headers=HEADERS, allow_redirects=True)
                raw_bytes = raw_r.content
                if raw_bytes[:2] == b'\x1f\x8b':
                    import gzip
                    xml = gzip.decompress(raw_bytes).decode('utf-8')
                    findings["notes"] += "sitemap_gzip_decompressed_successfully. "
                else:
                    xml = raw_bytes.decode('utf-8', errors='ignore')
            except Exception as e:
                findings["notes"] += f"sitemap_raw_fetch_failed: {type(e).__name__}. "

        if "<sitemapindex" in xml:
            try:
                child_locs = parse_locs(xml)
                for child_loc in child_locs:
                    if "product" in child_loc.lower() or "collection" in child_loc.lower() or "category" in child_loc.lower():
                        st_child, xml_child, _, _ = _fetch_with_retry(child_loc, "sitemap_child", findings, retries=0)
                        if st_child == 200 and xml_child and "<urlset" in xml_child:
                            locs = parse_locs(xml_child)
                            for loc in locs:
                                loc = _ensure_primary_domain(loc, domain)
                                if "/products/" in loc or "/product/" in loc:
                                    products.append(loc)
                                elif "/collections/" in loc or "/product-category/" in loc:
                                    collections.append(loc)
                                elif any(p in loc.lower() for p in ["/policies/", "/pages/shipping", "/pages/returns", "/pages/faq", "/pages/contact"]):
                                    policies.append(loc)
            except ET.ParseError as e:
                findings["notes"] += f"sitemapindex_parse_error: {str(e)[:100]}. "
        elif "<urlset" in xml:
            try:
                locs = parse_locs(xml)
                for loc in locs:
                    loc = _ensure_primary_domain(loc, domain)
                    if "/products/" in loc or "/product/" in loc:
                        products.append(loc)
                    elif "/collections/" in loc or "/product-category/" in loc:
                        collections.append(loc)
                    elif any(p in loc.lower() for p in ["/policies/", "/pages/shipping", "/pages/returns", "/pages/faq", "/pages/contact"]):
                        policies.append(loc)
            except ET.ParseError as e:
                findings["notes"] += f"sitemap_parse_error: {str(e)[:100]}. "
        else:
            # WAF/BINARY DETECTION: Catch placeholder images (JPEG/Exif) or binary garbage
            if "Exif" in xml or "JFIF" in xml or (not xml.strip().startswith("<") and len(xml) > 1000):
                findings["notes"] += "sitemap_returned_non_xml_binary: server returned an image file instead of XML — likely a misconfigured route. "
            else:
                findings["notes"] += f"sitemap_unrecognized_format: len={len(xml)} preview={xml[:100]}. "

    if len(policies) < 2:
        st_hp, html_hp, homepage_url, _ = _fetch(urls["homepage"], "homepage_links", findings)
        if st_hp == 200:
            links = _extract_links(html_hp, homepage_url)
            for link in links:
                link = _ensure_primary_domain(link, domain)
                if _is_policy_link(link):
                    if link not in policies:
                        policies.append(link)
                        if len(policies) >= 4:
                            break

    # BULLETPROOF URL FILTER: Remove image/non-HTML files from product list
    NON_PAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.pdf', '.css', '.js')
    products = [
        p for p in products
        if not any(p.lower().split('?')[0].endswith(ext) for ext in NON_PAGE_EXTENSIONS)
    ]
    urls["products"] = products[:5]
    if collections:
        urls["collection"] = collections[0]
    urls["policies_discovered"] = policies

    if not products:
        # EXTRA MILE: Scrape homepage for product links if sitemap failed
        st_hp, html_hp, _, _ = _fetch(f"https://{domain}/", "hp_product_scrape", findings)
        if st_hp == 200 and html_hp:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_hp, 'html.parser')
            NON_PAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.pdf', '.css', '.js')
            for a in soup.find_all('a', href=True):
                href = a['href']
                classes = ' '.join(a.get('class', []))
                # DYNAMIC COMMERCE DETECTOR: URL paths + HTML signals (product-card, add-to-cart, shop, item)
                is_product_signal = any(p in href.lower() for p in ['/product/', '/products/', '/catalog/product/', '/p/'])
                is_class_signal = any(sig in classes.lower() for sig in ['product-card', 'product-item', 'add-to-cart', 'shop-now', 'buy-now'])
                
                if is_product_signal or is_class_signal:
                    full_url = urljoin(f"https://{domain}/", href)
                    if not any(full_url.lower().split('?')[0].endswith(ext) for ext in NON_PAGE_EXTENSIONS):
                        if full_url not in products:
                            products.append(full_url)
                            if len(products) >= 5:
                                break
            if products:
                findings["notes"] += f"dynamic_commerce_detection_used: {len(products)} products found via HTML/URL signals. "
        if not products:
            findings["notes"] += "sitemap_failed_to_yield_products. "

    # P0: Final Blacklist Filter to eradicate Gift Card bypass
    if "products" in urls:
        urls["products"] = [p for p in urls["products"] if not any(b in p.lower() for b in ["gift-card", "gift_card", "/search", "/policies/", "/cart", "/checkout", "/blogs/", "/account"])]
    return urls

def _check_crawlability(domain, findings):
    score = 10.0
    issues = []
    resources = {
        "robots.txt": f"https://{domain}/robots.txt",
        "llms.txt": f"https://{domain}/llms.txt",
        "llms-full.txt": f"https://{domain}/llms-full.txt",
        "agents.md": f"https://{domain}/agents.md"
    }
    results = {}
    blocked_resources = []

    for name, url in resources.items():
        st, text, final_url, ct = _fetch(url, name, findings)

        is_blocked = (st == 200 and _looks_blocked(text)) or st == 403 or st == 429
        if is_blocked:
            results[name] = "BLOCKED" if st == 200 else st
            blocked_resources.append(name)
            status_note = "WAF/bot-challenge" if st in [200, 403] else "Rate-Limited (429)"
            findings["notes"] += f"{name}: {status_note} (status {st}), treated as unreadable. "
            if name in ["llms.txt", "agents.md", "robots.txt"]:
                score -= 1.0
            continue

        results[name] = st

        if st == 200 and ("text" in str(ct) or "markdown" in str(ct) or name == "robots.txt"):
            if name == "llms.txt":
                parsed_final = urlparse(final_url or "")
                if parsed_final.netloc.lower() != domain and "checkout" in parsed_final.netloc.lower():
                    score -= 1.0
                    issues.append({
                        "code": "llms_txt_checkout_routing",
            "finding_id": "GEO-CRW-002",
                        "description": "llms.txt redirected to a checkout subdomain.",
                        "evidence": f"Final URL: {final_url}",
                        "affected_urls": [final_url],
                        "severity": "medium", "confidence": "VERIFIED",
                        "business_impact": "AI agents hitting payment domains may encounter strict bot-protection before catalog discovery.",
                        "difficulty": "Medium",
                        "fix": "Host AI discovery files on the primary brand CDN."
                    })
            if name == "robots.txt":
                ai_bots = ["GPTBot", "ClaudeBot", "PerplexityBot", "Google-Extended"]
                blocked = []
                current_agent = None
                for line in text.splitlines():
                    line_lower = line.lower()
                    if line_lower.startswith("user-agent:"):
                        current_agent = line.split(":", 1)[1].strip()
                    elif line_lower.startswith("disallow:") and current_agent in ai_bots:
                        if line.split(":", 1)[1].strip() == "/":
                            blocked.append(current_agent)
                if blocked:
                    score -= 2.0
                    issues.append({
                        "code": "ai_crawlers_blocked",
                        "description": f"robots.txt explicitly blocks AI engines: {', '.join(blocked)}.",
                        "evidence": "Disallow: / under specific AI user-agents.",
                        "affected_urls": [url],
                        "severity": "high", "confidence": "VERIFIED",
                        "business_impact": "Your brand is actively hidden from next-generation AI search engines (ChatGPT, Perplexity), ceding market share to competitors.",
                        "difficulty": "Easy",
                        "fix": "Update robots.txt to explicitly allow GPTBot, ClaudeBot, and PerplexityBot."
                    })
        else:
            if name in ["llms.txt", "agents.md", "robots.txt"]:
                score -= 1.0

    if len(blocked_resources) == len(resources):
        findings["dimensions_measured"]["crawlability"] = False
        issues.append({
            "code": "crawlability_unmeasured",
            "description": "All crawlability resources returned bot-challenge pages instead of real content.",
            "evidence": f"Blocked: {', '.join(blocked_resources)}.",
            "affected_urls": list(resources.values()),
            "severity": "medium", "confidence": "UNVERIFIED",
            "business_impact": "Crawlability is unknown. The site's WAF may also be blocking legitimate AI crawlers (e.g. GPTBot).",
            "difficulty": "Medium",
            "fix": "Manually verify robots.txt/llms.txt accessibility, and check WAF bot-protection rules.",
        })

    findings["dimensions"]["crawlability"] = max(0, score)
    findings["issues"].extend(issues)
    findings["crawlability_matrix"] = results

def _check_answerability(domain, sample_urls, findings):
    score = 10.0
    issues = []
    policy_urls = sample_urls.get("policies_discovered", [])

    if len(policy_urls) < 2:
        st, html, homepage_url, _ = _fetch(sample_urls["homepage"], "homepage_links", findings)
        if st == 200:
            links = _extract_links(html, homepage_url)
            for link in links:
                link = _ensure_primary_domain(link, domain)
                if _is_policy_link(link):
                    if link not in policy_urls:
                        policy_urls.append(link)
                        if len(policy_urls) >= 4:
                            break

    found_policies = []
    weak_policies = []

    for url in policy_urls[:4]:
        if url.rstrip('/') == sample_urls["homepage"].rstrip('/'):
            continue
        st, text, final_url, _ = _fetch(url, "policy", findings)
        if st == 200:
            soup = BeautifulSoup(text, 'html.parser')
            clean_text = soup.get_text(separator=' ', strip=True)
            word_count = len(clean_text.split())
            if word_count > 100:
                found_policies.append(final_url)
            else:
                weak_policies.append(final_url)

    if len(found_policies) < 2:
        score -= 4.0
        issues.append({
            "code": "missing_answerability_content",
            "description": "Core commercial policies (Shipping, Returns, FAQ) are missing or lack substantive content.",
            "evidence": f"Found {len(found_policies)} strong policy pages. Weak pages: {len(weak_policies)}.",
            "affected_urls": policy_urls if policy_urls else [sample_urls["homepage"]],
            "severity": "medium", "confidence": "VERIFIED",
            "business_impact": "Missing structured answers may reduce visibility and trust in conversational commerce and AI-assisted discovery.",
            "difficulty": "Easy",
            "fix": "Publish comprehensive, text-rich policy and FAQ pages to capture AI-driven customer support queries."
        })

    findings["dimensions"]["answerability"] = max(0, score)
    findings["issues"].extend(issues)
    findings["answerability_matrix"] = {
        "strong_policies": len(found_policies),
        "weak_policies": len(weak_policies)
    }


def _extract_real_assets(html, url, domain):
    if not html: return {}
    # WAF GUARD: If this is a challenge page, do not scrape it for brand data
    html_lower = html[:2000].lower() if html else ""
    if any(sig in html_lower for sig in ["just a moment", "window._cf_chl_opt", "captcha", "challenge-platform", "enable javascript and cookies"]):
        return {"brand_name": domain.split('.')[0].capitalize(), "logo_url": f"https://{domain}/favicon.ico", "socials": [], "product_name": "REPLACE_WITH_PRODUCT_NAME", "product_desc": "REPLACE_WITH_PRODUCT_DESCRIPTION", "price": "NOT_DETECTED", "sku": "NOT_DETECTED", "product_url": url}
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    assets = {}
    
    # Brand/Site Name
    og_site = soup.find("meta", property="og:site_name")
    title = soup.find("title")
    assets["brand_name"] = (og_site["content"] if og_site else (title.text.split('|')[0].split('-')[0].strip() if title else domain))
    
    # Logo
    og_logo = soup.find("meta", property="og:image")
    icon = soup.find("link", rel=lambda x: x and 'icon' in x.lower())
    assets["logo_url"] = (og_logo["content"] if og_logo else (icon["href"] if icon else f"https://{domain}/favicon.ico")).replace("http://", "https://")
    
    # Socials
    socials = []
    for a in soup.find_all("a", href=True):
        href = a["href"].lower()
        if any(s in href for s in ["facebook.com", "twitter.com", "instagram.com", "linkedin.com", "youtube.com", "tiktok.com"]):
            if href not in socials: socials.append(href)
    assets["socials"] = [s for s in socials[:3] if s and s.startswith("http")]
    
    # Product Specifics
    og_title = soup.find("meta", property="og:title")
    h1_tag = soup.find('h1')
    h1_text = h1_tag.get_text(strip=True) if h1_tag else ""
    og_text = og_title["content"] if og_title else ""
    
    # Industrial Cascade: JSON-LD (handled elsewhere) -> OG Title -> H1 -> UNKNOWN
    if og_text and og_text != assets["brand_name"] and og_text.lower() != domain.lower():
        assets["product_name"] = og_text
    elif h1_text and h1_text != assets["brand_name"] and h1_text.lower() != domain.lower():
        assets["product_name"] = h1_text
    else:
        assets["product_name"] = "REPLACE_WITH_PRODUCT_NAME"
    assets["product_url"] = url
    desc_meta = soup.find("meta", property="og:description") or soup.find("meta", attrs={"name": "description"})
    assets["product_desc"] = (desc_meta["content"] if desc_meta else "REPLACE_WITH_PRODUCT_DESCRIPTION")
    
    price_meta = soup.find("meta", property="product:price:amount") or soup.find("meta", attrs={"itemprop": "price"})
    assets["price"] = (price_meta["content"] if price_meta else "REPLACE_WITH_PRICE")
    
    sku_meta = soup.find("meta", property="product:retailer_item_id") or soup.find("meta", attrs={"itemprop": "sku"})
    assets["sku"] = (sku_meta["content"] if sku_meta else "REPLACE_WITH_SKU")
    
    return assets


def _analyze_entities_and_products(domain, sample_urls, findings):
    entity_score = 10.0
    issues = []
    platform = findings.get("platform_detected", "unknown")
    is_commerce = bool(sample_urls.get("products") or sample_urls.get("collection") or platform in ["shopify", "woocommerce", "bigcommerce", "magento", "salesforce", "vtex"])
    
    # HTML COMMERCE OVERRIDE: If sitemap failed, check homepage for cart/shopify signals
    if not is_commerce and sample_urls.get("homepage"):
        hp_st, hp_html, _, _ = _fetch(sample_urls["homepage"], "hp_commerce_check", findings)
        if hp_st == 200 and hp_html:
            hp_lower = hp_html.lower()
            commerce_signals = ["window.shopify", "shopify.shop", "add-to-cart", "addtobag", "add to bag", "product-card", "woocommerce", "product_type", "dw.__version__", "vtex", "salesforce", "buy now", "price", "cart", "checkout", "shop"]
            if any(sig in hp_lower for sig in commerce_signals):
                is_commerce = True
                findings["notes"] += "commerce_detected_via_html_signals. "
            else:
                # ENTERPRISE LINK SCRAPE: Check <a href="..."> for /product/, /cart/, /shop/
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(hp_html, 'html.parser')
                links = [a.get('href', '') for a in soup.find_all('a', href=True)]
                commerce_urls = [l for l in links if any(p in l.lower() for p in ["/product/", "/products/", "/cart", "/checkout", "/shop/", "/collections/", "/categories/"])]
                if commerce_urls:
                    is_commerce = True
                    findings["notes"] += f"commerce_detected_via_link_scrape ({len(commerce_urls)} URLs). "
                else:
                    # ROBOTS.TXT COMMERCE FALLBACK (Catches CSR sites where links are JS-injected)
                    robots_st, robots_txt, _, _ = _fetch(f"https://{domain}/robots.txt", "robots_commerce", findings)
                    if robots_st == 200 and robots_txt:
                        robots_lower = robots_txt.lower()
                        if any(path in robots_lower for path in ["/cart", "/checkout", "/product", "/shop", "/collections"]):
                            is_commerce = True
                            findings["notes"] += "commerce_detected_via_robots_txt. "

    # COMMERCE GATE: If no products/cart found, do not audit as e-commerce
    if not is_commerce:
        findings["dimensions_measured"]["product_intelligence"] = False
        findings["dimensions_measured"]["agentic_commerce"] = False
        issues.append({
            "code": "non_commerce_profile",
            "description": "Site appears to be a brand/corporate profile, not a direct e-commerce store.",
            "evidence": "No product URLs or cart functionality detected in sitemap or navigation.",
            "affected_urls": [sample_urls.get("homepage", f"https://{domain}/")],
            "severity": "low", "confidence": "VERIFIED",
            "business_impact": "Standard e-commerce revenue leak metrics do not apply.",
            "difficulty": "N/A", "fix": "N/A"
        })
        findings["dimensions"]["entity_intelligence"] = 10.0 # Assume entity is fine if not commerce
        findings["issues"].extend(issues)
        return

    all_nodes = []
    entity_pages_found = 0
    total_pages_crawled = 0
    csr_pages = 0
    redirect_shell_pages = 0

    urls_to_crawl = [sample_urls["homepage"]]
    if "collection" in sample_urls: urls_to_crawl.append(sample_urls["collection"])
    urls_to_crawl.extend(sample_urls.get("products", []))

    for url in urls_to_crawl:
        st, html, final_url, _ = _fetch(url, "crawl", findings)
        if st == 200:
            total_pages_crawled += 1
            nodes = _extract_json_ld(html)
            all_nodes.extend(nodes)

            is_redirect_shell = False
            if final_url:
                final_netloc = urlparse(final_url).netloc.replace("www.", "")
                base_domain = domain.replace("www.", "")
                if final_netloc != base_domain:
                    is_redirect_shell = True

            if len(nodes) == 0:
                if is_redirect_shell: redirect_shell_pages += 1
                else: csr_pages += 1

            # GRAPH-AWARE ENTITY DETECTION
            has_entity = False
            for node in nodes:
                if isinstance(node, dict):
                    t = node.get("@type", "")
                    if isinstance(t, list): t = " ".join(t)
                    # Check for Organization, Brand, or WebSite->publisher
                    if any(x in t for x in ["Organization", "Corporation", "Brand", "WebSite"]):
                        has_entity = True
                    # Check Product->brand
                    if "Product" in t and node.get("brand"): has_entity = True
            if has_entity: entity_pages_found += 1

    if total_pages_crawled > 0:
        if (redirect_shell_pages / total_pages_crawled) > 0.5:
            issues.append({
                "code": "redirect_shell_detected",
            "finding_id": "GEO-CRW-001",
                "description": "Core pages redirect to external shells (e.g., checkout subdomains) with no schema.",
                "evidence": f"{redirect_shell_pages}/{total_pages_crawled} pages redirected to external domains without returning schema.",
                "affected_urls": urls_to_crawl, "severity": "high", "confidence": "VERIFIED",
                "business_impact": "AI agents are routed to payment/external domains and blocked before seeing catalog data.",
                "difficulty": "Medium", "fix": "Ensure core merchandising URLs resolve on the primary domain."
            })
        elif (csr_pages / total_pages_crawled) > 0.5:
            issues.append({
                "code": "csr_schema_leak",
            "finding_id": "GEO-CSR-001",
                "description": "Client-Side Rendering (CSR) is preventing raw HTML schema extraction.",
                "evidence": f"{csr_pages}/{total_pages_crawled} sampled pages return 0 JSON-LD blocks in raw HTML.",
                "affected_urls": urls_to_crawl, "severity": "high", "confidence": "VERIFIED",
                "business_impact": "Lightweight AI shopping agents that do not execute JavaScript will see 0% entity and product data.",
                "difficulty": "Hard", "fix": "Implement Server-Side Rendering (SSR) or Static Site Generation (SSG).",
                "fix_snippet": _generate_snippet("organization", domain)
            })

    # DEDUPLICATION: Removed redundant entity consistency check to prevent double-counting.

    flat_nodes = []
    for g in all_nodes:
        if isinstance(g, dict):
            if "@graph" in g: flat_nodes.extend([n for n in g["@graph"] if isinstance(n, dict)])
            else: flat_nodes.append(g)

    has_org, has_same_as = False, False
    for node in flat_nodes:
        t = node.get("@type", "")
        if isinstance(t, list): t = " ".join(t)
        if any(x in t for x in ["Organization", "Corporation", "Brand"]):
            has_org = True
            if node.get("sameAs"): has_same_as = True

    if not has_org:
        entity_score -= 5.0
        # Check if entity is defined via other schema types (Partner Fix #6)
        has_other_entity = False
        for node in flat_nodes:
            t = node.get("@type", "")
            if isinstance(t, list): t = " ".join(t)
            if any(x in t for x in ["WebSite", "WebPage", "Product", "LocalBusiness"]):
                has_other_entity = True
                break
        
        ent_severity = "medium" if has_other_entity else "high"
        ent_desc = "Missing explicit Organization JSON-LD (Entity signals detected via other schema types)." if has_other_entity else "Missing Organization/Brand schema in JSON-LD."
        
        issues.append({
            "code": "missing_organization_entity",
            "finding_id": "GEO-ENT-001",
            "description": ent_desc,
            "observed": "No Organization, Corporation, or Brand node found in JSON-LD.",
            "evidence": "Parsed JSON-LD structures on homepage and sampled product pages.",
            "inference": "Adding explicit Organization structured data significantly increases the probability that AI systems will accurately identify and recommend your brand.",
            "recommendation": "Add or consolidate Organization/Brand structured data.",
            "affected_urls": urls_to_crawl, "severity": ent_severity, "confidence": "VERIFIED",
            "business_impact": ISSUE_COPY.get("missing_organization_entity", {}).get("business_impact", "Reduces explicit machine-readable entity clarity."),
            "difficulty": "Easy", "fix": "Add or consolidate Organization/Brand structured data.",
            "fix_snippet": _generate_snippet("organization", domain)
        })
    elif not has_same_as:
        entity_score -= 2.0
        issues.append({
            "code": "incomplete_entity_corroboration",
            "description": "Organization exists, but lacks a sameAs trust chain.",
            "evidence": "sameAs array missing or empty.",
            "affected_urls": urls_to_crawl, "severity": "medium", "confidence": "VERIFIED",
            "business_impact": "Entity corroboration is incomplete.",
            "difficulty": "Easy", "fix": "Add Wikipedia and social URLs to sameAs."
        })

    findings["dimensions"]["entity_intelligence"] = max(0, entity_score)
    
    # PRODUCT "MONEY LEAK" DETECTOR
    products = sample_urls.get("products", [])
    if products:
        product_scores = []

        field_totals = {'name': 0, 'image': 0, 'price': 0, 'avail': 0, 'sku': 0, 'brand': 0}

        valid_p_count = 0
        for p_url in products:
            st, html, final_url, _ = _fetch(p_url, "product", findings)
            if st == 200:
                nodes = _extract_json_ld(html)
                p_score = 0
                has_prod = has_name = has_image = has_offers = has_price = has_avail = has_var = has_sku = has_brand = has_review = False
                for node in nodes:
                    if isinstance(node, dict):
                        t = node.get("@type", "")
                        if isinstance(t, list): t = " ".join(t)
                        if "Product" in t:
                            has_prod = True
                            if node.get("name"): has_name = True
                            if node.get("image"): has_image = True
                            if node.get("sku") or node.get("gtin") or node.get("mpn"): has_sku = True
                            if node.get("brand"): has_brand = True
                            if node.get("review") or node.get("aggregateRating"): has_review = True
                            if node.get("offers"):
                                has_offers = True
                                offers = node["offers"]
                                if isinstance(offers, list): offers = offers[0] if offers else {}
                                if isinstance(offers, dict):
                                    if offers.get("price") or offers.get("lowPrice"): has_price = True
                                    if offers.get("availability"): has_avail = True
                            if node.get("hasVariant") or node.get("variants"): has_var = True
                
                # TIER 1 FALLBACK: Check standard meta tags if JSON-LD is missing/empty
                if p_score == 0 and html:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Flexible OG/Meta detection
                    og_type = soup.find("meta", property="og:type")
                    if og_type and "product" in og_type.get("content", "").lower(): has_prod = True
                    if soup.find("meta", property=re.compile(r"product:price")): has_price = True
                    if soup.find("meta", property=re.compile(r"product:availability")): has_avail = True
                    if soup.find("meta", property=re.compile(r"product:brand")): has_brand = True
                    if soup.find("meta", property=re.compile(r"product:retailer_item_id")) or soup.find("meta", attrs={"name": "sku"}): has_sku = True
                    if soup.find("meta", property=re.compile(r"og:title")) or soup.find("title"): has_name = True
                    if soup.find("meta", property=re.compile(r"og:image")): has_image = True

                # ENTERPRISE META-TAG EXTRACTION (Runs in parallel with JSON-LD)
                if html and p_score < 50:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(html, 'html.parser')
                    og_type = soup.find("meta", property="og:type")
                    if og_type and "product" in og_type.get("content", "").lower(): has_prod = True
                    if soup.find("meta", property=re.compile(r"product:price")) or soup.find("meta", attrs={"itemprop": "price"}): has_price = True
                    if soup.find("meta", property=re.compile(r"product:availability")) or soup.find("meta", attrs={"itemprop": "availability"}): has_avail = True
                    if soup.find("meta", property=re.compile(r"product:brand")) or soup.find("meta", attrs={"itemprop": "brand"}): has_brand = True
                    if soup.find("meta", property=re.compile(r"product:retailer_item_id")) or soup.find("meta", attrs={"itemprop": "sku"}): has_sku = True
                    if soup.find("meta", property=re.compile(r"og:title")) or soup.find("title"): has_name = True
                    if soup.find("meta", property=re.compile(r"og:image")): has_image = True

                # Tier 1 Scoring
                if has_name: p_score += 15
                if has_image: p_score += 10
                if has_price: p_score += 20
                if has_avail: p_score += 20
                if has_sku: p_score += 20
                if has_brand: p_score += 15
                
                # Accumulate forensic totals

                
                valid_p_count += 1

                
                if has_name: field_totals['name'] += 1

                
                if has_image: field_totals['image'] += 1

                
                if has_price: field_totals['price'] += 1

                
                if has_avail: field_totals['avail'] += 1

                
                if has_sku: field_totals['sku'] += 1

                
                if has_brand: field_totals['brand'] += 1


                
                product_scores.append(min(100, p_score))

        if product_scores:
            avg_prod_score = sum(product_scores) / len(product_scores)
            findings["dimensions"]["product_intelligence"] = avg_prod_score / 10.0
            findings["dimensions_measured"]["product_intelligence"] = True

            if avg_prod_score < 80:
                # Calculate exact missing counts for traceable evidence
                missing_fields = []
                if field_totals['price'] < valid_p_count: missing_fields.append(f"price ({valid_p_count - field_totals['price']}/{valid_p_count})")
                if field_totals['avail'] < valid_p_count: missing_fields.append(f"availability ({valid_p_count - field_totals['avail']}/{valid_p_count})")
                if field_totals['sku'] < valid_p_count: missing_fields.append(f"SKU/GTIN ({valid_p_count - field_totals['sku']}/{valid_p_count})")
                if field_totals['brand'] < valid_p_count: missing_fields.append(f"brand ({valid_p_count - field_totals['brand']}/{valid_p_count})")
                
                issues.append({
                    "code": "incomplete_product_schema",
            "finding_id": "GEO-PRD-001",
                    "description": f"Product schema is {avg_prod_score:.0f}% complete. Missing attributes reduce AI-shopping eligibility.",
                    "finding_id": "GEO-PRD-001",
                    "dimension": "Product Intelligence",
                    "observation": f"Sampled {valid_p_count} verified product pages. Missing: {', '.join(missing_fields) if missing_fields else 'None'}.",
                    "evidence": f"Sampled {valid_p_count} products. Forensic Coverage: Name {int(field_totals['name']/max(1,valid_p_count)*100)}% | Image {int(field_totals['image']/max(1,valid_p_count)*100)}% | Price {int(field_totals['price']/max(1,valid_p_count)*100)}% | Avail {int(field_totals['avail']/max(1,valid_p_count)*100)}% | SKU {int(field_totals['sku']/max(1,valid_p_count)*100)}% | Brand {int(field_totals['brand']/max(1,valid_p_count)*100)}%.",
                    "affected_urls": products, "severity": "high", "confidence": "VERIFIED",
                    "business_impact": ISSUE_COPY.get("incomplete_product_schema", {}).get("business_impact", "Incomplete machine-readable product data may reduce eligibility."),
                    "difficulty": "Medium", "fix": "Ensure Product schema includes exact price, availability, and SKU/GTIN identifiers to capture AI-driven market share.",
                    "fix_snippet": _generate_snippet("product", domain, "NOT_DETECTED")
                })
        else:
            findings["dimensions_measured"]["product_intelligence"] = False
            findings["dimensions"]["product_intelligence"] = None
            issues.append({
                "code": "product_intelligence_unknown",
                "description": "Product pages were found but could not be crawled or returned no schema.",
                "evidence": f"Sampled {len(products)} products, but 0 returned valid schema.",
                "affected_urls": products, "severity": "medium", "confidence": "UNVERIFIED",
                "business_impact": "Product schema quality is unknown (Audit Limitation).",
                "difficulty": "Medium", "fix": "Verify product pages are accessible to crawlers."
            })
    else:
        findings["dimensions_measured"]["product_intelligence"] = False
        findings["dimensions"]["product_intelligence"] = None
        
        issues.append({
            "code": "product_intelligence_unknown",
            "description": "No product pages could be sampled.",
            "evidence": findings["notes"],
            "affected_urls": [], "severity": "medium", "confidence": "UNVERIFIED",
            "business_impact": "Product schema quality is unknown (Audit Limitation).",
            "difficulty": "Medium", "fix": "Verify sitemap contains product URLs."
        })
    findings["issues"].extend(issues)


def _check_agentic_commerce(domain, findings):
    capabilities = {"Discovery": "FAIL", "UCP": "FAIL", "MCP": "FAIL", "Catalog": "FAIL", "Cart/Checkout": "FAIL"}
    score = 0.0

    st_ucp, ucp_body, final_url, ct_ucp = _fetch(f"https://{domain}/.well-known/ucp", "ucp", findings)
    if st_ucp == 200 and not _is_soft_404(ucp_body, ct_ucp):
        capabilities["Discovery"] = "PASS"
        capabilities["UCP"] = "PASS"
        score += 4.0

    mcp_endpoint = None
    if st_ucp == 200:
        try:
            data = json.loads(ucp_body)
            for svc_list in data.get("ucp", {}).get("services", {}).values():
                if isinstance(svc_list, list):
                    for svc in svc_list:
                        if "endpoint" in svc:
                            mcp_endpoint = svc["endpoint"]
                            break
            if mcp_endpoint and not mcp_endpoint.startswith("http"):
                mcp_endpoint = urljoin(f"https://{domain}", mcp_endpoint)
        except Exception:
            pass

    if mcp_endpoint:
        # FIXED: Moved PASS assignment to successful handshake
            # capabilities["MCP"] = "PASS"
        # Score moved to successful handshake
        try:
            payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
            headers = {"Content-Type": "application/json", "Accept": "application/json"}
            if USE_STEALTH:
                r = cffi_requests.post(mcp_endpoint, json=payload, headers=headers, timeout=TIMEOUT, impersonate="chrome120")
            else:
                r = std_requests.post(mcp_endpoint, json=payload, headers=headers, timeout=TIMEOUT)

            if r.status_code == 200:
                score += 2.0  # Awarded ONLY after successful handshake
                capabilities["MCP"] = "PASS"
                data = json.loads(r.text)
                tools = {t.get("name", "").lower() for t in data.get("result", {}).get("tools", [])}
                if any("search" in t or "catalog" in t or "product" in t for t in tools):
                    capabilities["Catalog"] = "PASS"
                    score += 2.0
                if any("cart" in t or "checkout" in t for t in tools):
                    capabilities["Cart/Checkout"] = "PASS"
                    score += 2.0
            else:
                findings["issues"].append({
                    "code": "mcp_handshake_failed",
                    "description": "MCP endpoint returned error during JSON-RPC handshake.",
                    "evidence": f"POST {mcp_endpoint} -> {r.status_code}",
                    "affected_urls": [mcp_endpoint],
                    "severity": "high", "confidence": "VERIFIED",
                    "business_impact": "Agentic checkout pipes are broken. AI agents cannot transact.",
                    "difficulty": "Hard",
                    "fix": "Debug MCP server routing and ensure public JSON-RPC access."
                })
        except Exception as e:
            findings["notes"] += f"MCP exception: {e}. "

    # Sanitize Agentic Matrix & Fix Contradiction (Partner Fix #18)
    plat = findings.get("platform_detected", "unknown")
    if plat not in ["custom_headless", "api_first"]:
        capabilities = {k: ("NOT_DETECTED" if v == "FAIL" else v) for k, v in capabilities.items()}
        # If standard platform and no agentic protocols found, cap score at baseline 5.0
        if score == 0.0:
            score = 5.0 
            findings["notes"] += "agentic_score_capped_at_standard_baseline. "

    # P0: Agentic Cap - MCP/Catalog/Checkout rules enforced
    if capabilities.get("MCP") in ["NOT_DETECTED", "FAIL"]: score = min(score, 8.0)
    if capabilities.get("Catalog") in ["NOT_DETECTED", "FAIL"] or capabilities.get("Cart/Checkout") in ["NOT_DETECTED", "FAIL"]: score = min(score, 6.0)
    # P0: Agentic Cap - MCP/Catalog/Checkout rules enforced
    if capabilities.get("MCP") in ["NOT_DETECTED", "FAIL"]: score = min(score, 8.0)
    if capabilities.get("Catalog") in ["NOT_DETECTED", "FAIL"] or capabilities.get("Cart/Checkout") in ["NOT_DETECTED", "FAIL"]: score = min(score, 6.0)
    findings["dimensions"]["agentic_commerce"] = score
    findings["agentic_capabilities"] = capabilities
    
    if capabilities["UCP"] == "PASS" and (capabilities["Catalog"] == "FAIL" or capabilities["Cart/Checkout"] == "FAIL"):
        findings["issues"].append({
            "code": "agentic_commerce_partial",
            "description": "UCP discovery file exists, but the MCP tool handshake for Catalog/Cart failed.",
            "evidence": f"Capabilities: {capabilities}",
            "affected_urls": [f"https://{domain}/.well-known/ucp"],
            "severity": "medium", "confidence": "VERIFIED",
            "business_impact": "AI shopping agents can discover the store via UCP but cannot execute MCP tool calls to browse or transact.",
            "difficulty": "Medium",
            "fix": "Check product feed completeness and MCP endpoint health."
        })

def audit_geo(domain: str) -> dict:
    # OG Input Sanitization: Strip protocols and paths from dirty API data
    if domain.startswith("http://") or domain.startswith("https://"):
        from urllib.parse import urlparse
        domain = urlparse(domain).netloc
    domain = domain.split('/')[0].strip()

    findings = {
        "domain": domain,
        "platform_detected": "unknown",
        "issues": [],
        "notes": "",
        "business_interpretation": [],
        "dimensions": {
            "crawlability": 10.0,
            "entity_intelligence": 10.0,
            "product_intelligence": 10.0,
            "answerability": 10.0,
            "agentic_commerce": 0.0
        },
        "dimensions_measured": {
            "crawlability": True,
            "entity_intelligence": True,
            "product_intelligence": False,
            "answerability": True,
            "agentic_commerce": True
        },
        "crawlability_matrix": {},
        "agentic_capabilities": {},
        "answerability_matrix": {"strong_policies": 0, "weak_policies": 0}
    }

    if not _check_domain_reachable(domain, findings):
        findings["overall_geo_score"] = None
        findings["score_confidence"] = "unreachable"
        findings["issues"] = [{
            "code": "domain_unreachable",
            "description": f"{domain} did not respond to any request - ikely wrong domain, DNS failure, or site offline.",
            "evidence": findings["notes"],
            "affected_urls": [],
            "severity": "high", "confidence": "VERIFIED",
            "business_impact": "Cannot audit a site that cannot be reached.",
            "difficulty": "N/A",
            "fix": "Verify the domain is correct and the site is live before re-running.",
        }]
        return findings

    sample_urls = _sample_urls(domain, findings)
    
    # Enterprise Reality: Strict Product URL Blacklist applied to all sampled URLs
    _BL = ['gift-card', 'gift_card', '/search', '/policies/', '/cart', '/checkout', '/blogs/', '/account', '/login', '/password', '/contact-us', '/faq', '/apps/']
    for k in list(sample_urls.keys()):
        if isinstance(sample_urls[k], list):
            sample_urls[k] = [u for u in sample_urls[k] if not any(b in u.lower() for b in _BL)]

    # OG ROBUST PLATFORM DETECTION (Fallback chain)
    platform = findings.get("platform_detected", "unknown")
    if platform == 'unknown':
        st, html, _, hdrs = _fetch(f"https://{domain}/", "plat_hp", findings)
        if st == 200 and html: platform = _detect_platform(html, hdrs)
        
    if platform == 'unknown':
        st, html, _, hdrs = _fetch(f"https://www.{domain}/", "plat_www", findings)
        if st == 200 and html: platform = _detect_platform(html, hdrs)
        
    if platform == 'unknown' and sample_urls.get("products"):
        st, html, _, hdrs = _fetch(sample_urls["products"][0], "plat_prod", findings)
        if st == 200 and html: platform = _detect_platform(html, hdrs)
        
    if platform == 'unknown' and sample_urls.get("collection"):
        st, html, _, hdrs = _fetch(sample_urls["collection"], "plat_coll", findings)
        if st == 200 and html: platform = _detect_platform(html, hdrs)
        
    findings["platform_detected"] = platform

    try:
        _check_crawlability(domain, findings)
    except Exception as e:
        findings["notes"] += f"crawlability_crash: {type(e).__name__}. "
    try:
        _check_answerability(domain, sample_urls, findings)
    except Exception as e:
        findings["notes"] += f"answerability_crash: {type(e).__name__}. "
    try:
        _analyze_entities_and_products(domain, sample_urls, findings)
    except Exception as e:
        findings["notes"] += f"entity_product_crash: {type(e).__name__}. "
    try:
        _check_agentic_commerce(domain, findings)
    except Exception as e:
        findings["notes"] += f"agentic_crash: {type(e).__name__}. "


    dims = findings["dimensions"]
    measured = findings["dimensions_measured"]
    
    # Fix 1: No perfect score for unknown data
    for k in WEIGHTS:
        if not measured.get(k, True):
            dims[k] = None

    active_weights = {k: WEIGHTS[k] for k in WEIGHTS if measured.get(k, True)}
    weight_total = sum(active_weights.values())
    total_possible_weight = sum(WEIGHTS.values())

    if weight_total == 0:
        overall = 0.0
    else:
        # Calculate score based only on measured dimensions (Unknown != 0)
        measured_score = sum(dims[k] * active_weights[k] for k in active_weights) / weight_total
        
        # Confidence Penalty: If >30% of weight is unmeasured, cap the score
        confidence_ratio = weight_total / total_possible_weight
        if confidence_ratio < 0.7:
            overall = measured_score * confidence_ratio
        else:
            overall = measured_score

    findings["overall_geo_score"] = round(overall, 1)
    findings["score_confidence"] = (
        "full" if weight_total == sum(WEIGHTS.values()) else "partial"
    )

    if dims.get("entity_intelligence") is not None and dims["entity_intelligence"] < 8:
        findings["business_interpretation"].append("While your brand has strong market presence, adding explicit machine-readable Organization signals significantly increases the probability and accuracy of AI systems recommending you over competitors.")
    if dims.get("product_intelligence") is not None and dims["product_intelligence"] < 8:
        findings["business_interpretation"].append("Critical commerce attributes such as pricing, availability, and product identifiers are incomplete in the sampled machine-readable product data, which may reduce eligibility or reliability across search and AI-assisted shopping surfaces.")
    if dims.get("agentic_commerce") is not None and dims["agentic_commerce"] < 10:
        findings["business_interpretation"].append("Your infrastructure is currently invisible to next-generation agentic commerce protocols, ceding market share in the emerging AI-driven shopping ecosystem.")

    # ENTERPRISE SNIPPET INJECTION: Replace placeholders with real scraped assets
    hp_st, hp_html, _, _ = _fetch(f"https://{domain}/", "hp_snippet_assets", findings)
    real_assets = _extract_real_assets(hp_html, f"https://{domain}/", domain)
    
    for issue in findings.get("issues", []):
        if "fix_snippet" in issue and "REPLACE_WITH" in issue["fix_snippet"]:
            snippet = issue["fix_snippet"]
            snippet = snippet.replace("REPLACE_WITH_BRAND_NAME", real_assets.get("brand_name", domain).replace('"', '\\"'))
            snippet = snippet.replace("REPLACE_WITH_LOGO_URL", real_assets.get("logo_url", f"https://{domain}/favicon.ico"))
            socials_list = [s for s in real_assets.get("socials", []) if s and s.startswith("http")]
            snippet = snippet.replace("REPLACE_WITH_SOCIAL_URLS", '", "'.join(socials_list) if socials_list else "https://www.linkedin.com/company/REPLACE_WITH_COMPANY")
            
            # Product specific replacements
            if "REPLACE_WITH_IMAGE_URL" in snippet or "NOT_DETECTED" in snippet:
                p_url = issue["affected_urls"][0] if issue.get("affected_urls") else f"https://{domain}/"
                p_st, p_html, _, _ = _fetch(p_url, "prod_snippet_assets", findings)
                p_assets = _extract_real_assets(p_html, p_url, domain)
                snippet = snippet.replace("NOT_DETECTED", _sanitize_product_name(p_assets.get("product_name"), domain, real_assets.get("brand_name", "")).replace('"', '\"'))
                snippet = snippet.replace("REPLACE_WITH_IMAGE_URL", p_assets.get("logo_url", f"https://{domain}/logo.png"))
                snippet = snippet.replace("REPLACE_WITH_DESCRIPTION", p_assets.get("product_desc", "REPLACE_WITH_PRODUCT_DESCRIPTION").replace('"', '\"'))
                snippet = snippet.replace("REPLACE_WITH_SKU", p_assets.get("sku", "NOT_DETECTED"))
                snippet = snippet.replace("REPLACE_WITH_PRODUCT_URL", p_url)
                snippet = snippet.replace(f"https://{domain}/https://{domain}/", f"https://{domain}/")
                snippet = snippet.replace(f"https://{domain}/https://", "https://")
                snippet = snippet.replace("REPLACE_WITH_PRICE", p_assets.get("price", "NOT_DETECTED"))
                
                        # P0 Directive: Withhold executable snippet if critical data is unverified
            if "REPLACE_WITH_SKU" in snippet or "REPLACE_WITH_PRICE" in snippet or "REPLACE_WITH_PRODUCT_NAME" in snippet:
                issue["fix_snippet"] = "<!-- Fix snippet withheld: required commerce data (SKU/Price/Name) could not be verified from the audited page. -->\n<!-- Implementation guidance: Add valid Schema.org Product and Offer properties to the product template. -->"
            else:
                # P0: Withhold if unresolved
                if "REPLACE_WITH_" in snippet or "NOT_DETECTED" in snippet:
                    issue["fix_snippet"] = "<!-- Fix snippet withheld -->"
                else:
                    issue["fix_snippet"] = snippet

    # ENTERPRISE CLEANUP: Remove non_commerce_profile if commerce signals or WAFs were found
    notes = findings.get("notes", "")
    crawl_matrix = str(findings.get("crawlability_matrix", {}))
    commerce_confirmed = "commerce_detected_via" in notes
    
    # WAF HEURISTIC: Sites with aggressive 403/WAF blocks are high-traffic enterprise commerce, not blogs
    if "403" in crawl_matrix or "WAF" in notes or "bot-challenge" in notes:
        commerce_confirmed = True
        
    platform = findings.get("platform_detected", "unknown")
    if platform not in ["unknown", "custom_headless"]:
        commerce_confirmed = True

    if commerce_confirmed or findings.get("dimensions_measured", {}).get("product_intelligence") == True:
        findings["issues"] = [i for i in findings.get("issues", []) if i.get("code") != "non_commerce_profile"]
        
    # ENTERPRISE CLEANUP: Remove csr_schema_leak if product data was successfully extracted via meta/fallback
    if findings.get("dimensions", {}).get("product_intelligence") is not None and findings["dimensions"]["product_intelligence"] > 0:
        findings["issues"] = [i for i in findings.get("issues", []) if i.get("code") != "csr_schema_leak"]

    # ENTERPRISE SANITIZER: Clean binary garbage and truncate long previews
    import re as re_san
    import string
    printable = set(string.printable)
    
    def clean_text(text):
        if not text: return text
        # Remove binary headers like Exif, MM*, JFIF
        text = re_san.sub(r'(?i)(Exif|MM\*|JFIF|\x00|\ufffd)', '', text)
        # Keep only printable chars
        text = "".join(c for c in text if c in printable)
        # Truncate any preview with binary garbage
        if "preview=" in text:
            text = re_san.sub(r'preview=.*', 'preview=[BINARY_DATA_DISCARDED].', text)
        # Strip remaining non-XML garbage patterns
        text = re_san.sub(r'[A-Za-z]{1,3}\*[A-Za-z0-9$()]{2,}', '', text)
        text = re_san.sub(r'\s{2,}', ' ', text).strip()
        return text.strip()

    if "notes" in findings:
        findings["notes"] = clean_text(findings["notes"])
    for issue in findings.get("issues", []):
        if "evidence" in issue:
            issue["evidence"] = clean_text(issue["evidence"])
            
    # MCP CONTRADICTION FIX: If handshake failed with 403/404/Timeout, it's NOT_DETECTED, not broken
    for issue in findings.get("issues", []):
        if issue.get("code") in ["mcp_handshake_failed", "ucp_handshake_failed"]:
            evidence = issue.get("evidence", "")
            if "403" in evidence or "404" in evidence or "Timeout" in evidence:
                if "MCP" in findings.get("agentic_capabilities", {}):
                    findings["agentic_capabilities"]["MCP"] = "NOT_DETECTED"
                if "UCP" in findings.get("agentic_capabilities", {}):
                    findings["agentic_capabilities"]["UCP"] = "NOT_DETECTED"

    # Filter out MCP/UCP 403/404 issues (they are just missing endpoints, not broken pipes)
    findings["issues"] = [
        i for i in findings.get("issues", []) 
        if not (i.get("code") in ["mcp_handshake_failed", "ucp_handshake_failed"] and any(x in i.get("evidence", "") for x in ["403", "404", "Timeout"]))
    ]

    # WAF GUARDS: Suppress answerability hallucinations and infer enterprise platform
    notes = findings.get("notes", "")
    crawl_matrix = str(findings.get("crawlability_matrix", {}))
    is_waf_blocked = "403" in crawl_matrix or "WAF" in notes or "bot-challenge" in notes
    
    # REMOVED: Blanket WAF answerability suppression (Partner Fix #4)
        
    if findings.get("platform_detected") == "unknown" and is_waf_blocked:
        findings["platform_detected"] = "enterprise_waf_protected"

    # ENTITY GUARD: If massive timeouts/blocks occurred, entity score cannot be 10.0
    entity_notes = findings.get("notes", "")
    entity_matrix = findings.get("crawlability_matrix", {})
    all_blocked = all(v in [403, 429, "BLOCKED", None] for v in entity_matrix.values()) if entity_matrix else False
    many_timeouts = entity_notes.count("Timeout") >= 3
    if (all_blocked or many_timeouts) and findings.get("dimensions", {}).get("entity_intelligence") == 10.0:
        findings["dimensions"]["entity_intelligence"] = 5.0
        findings["notes"] += "entity_score_capped_insufficient_data. "

    # TIER 4 FILTER: Remove technical polish issues from headline revenue leaks
    findings["issues"] = [i for i in findings["issues"] if i.get("code") not in ["missing_breadcrumb_schema", "missing_faq_schema"]]
    
    # Evidence-Driven Confidence Calculation (Partner Directive #5)
    notes = findings.get("notes", "")
    if "timeout" in notes or "WAF" in notes or "bot-challenge" in notes or "binary_image" in notes or "unrecognized_format" in notes:
        findings["score_confidence"] = "PARTIAL"
    elif not findings.get("dimensions_measured", {}).get("product_intelligence", True):
        findings["score_confidence"] = "UNVERIFIED"
    else:
        findings["score_confidence"] = "VERIFIED"


    # Partner Directive: Reconcile Answerability Dimension
    try:
        ans_matrix = findings.get("answerability_matrix", {})
        strong_count = ans_matrix.get("strong_policies", 0)
        if strong_count == 0:
            findings["dimensions"]["answerability"] = min(findings["dimensions"].get("answerability", 10.0), 4.0)
        elif strong_count <= 2:
            findings["dimensions"]["answerability"] = min(findings["dimensions"].get("answerability", 10.0), 7.0)
    except Exception:
        pass
    return findings



def geo_opportunity_score(geo_findings: dict) -> float:
    score = geo_findings.get("overall_geo_score")
    return round(float(score), 1) if score is not None else 0.0