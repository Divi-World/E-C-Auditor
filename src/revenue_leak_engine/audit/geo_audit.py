import re
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

def _ensure_primary_domain(url_str, primary_domain):
    try:
        parsed = urlparse(url_str)
        if parsed.netloc != primary_domain and primary_domain in parsed.netloc:
            return parsed._replace(netloc=primary_domain).geturl()
        return url_str
    except Exception:
        return url_str

def _fetch(url, notes_key, findings):
    try:
        if USE_STEALTH:
            r = cffi_requests.get(url, timeout=TIMEOUT, impersonate="chrome120", allow_redirects=True)
        else:
            r = std_requests.get(url, timeout=TIMEOUT, headers=HEADERS, allow_redirects=True)
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
                r = std_requests.get(url, timeout=tout, headers=HEADERS, allow_redirects=True)
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

def _extract_json_ld(html):
    soup = BeautifulSoup(html, 'html.parser')
    parsed = []
    for script in soup.find_all('script', type='application/ld+json'):
        if script.string:
            text = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', script.string, flags=re.DOTALL).strip()
            try:
                parsed.append(json.loads(text))
            except json.JSONDecodeError:
                continue
    return parsed

def _extract_links(html, base_url):
    soup = BeautifulSoup(html, 'html.parser')
    links = []
    for a in soup.find_all('a', href=True):
        links.append(urljoin(base_url, a['href']))
    return links

def _detect_platform(html, headers):
    headers = headers or {}
    if "cdn.shopify.com" in html or headers.get("x-shopify-stage"):
        return "shopify"
    if "/wp-content/" in html or "/wp-json/" in html:
        return "woocommerce"
    if headers.get("x-powered-by", "").lower().startswith("next.js") or "__next" in html:
        return "custom_headless"
    for k, v in headers.items():
        if 'shopify' in str(v).lower() or k.lower() == 'x-shopid': return 'shopify'
    if 'myshopify.com' in html or 'shopify.com' in html: return 'shopify'
    if 'wp-content' in html or 'woocommerce' in html or 'wp-json' in html: return 'woocommerce'
    return 'unknown'

def _generate_snippet(code_type, domain, sample_name=""):
    if code_type == "organization":
        return '<script type="application/ld+json">\n{\n  "@context": "https://schema.org",\n  "@type": "Organization",\n  "name": "REPLACE_WITH_BRAND_NAME",\n  "url": "https://' + domain + '",\n  "logo": "REPLACE_WITH_LOGO_URL",\n  "sameAs": [ "REPLACE_WITH_SOCIAL_URLS" ]\n}\n</script>'
    elif code_type == "faq":
        return '<script type="application/ld+json">\n{\n  "@context": "https://schema.org",\n  "@type": "FAQPage",\n  "mainEntity": [{\n    "@type": "Question",\n    "name": "REPLACE_WITH_QUESTION",\n    "acceptedAnswer": {\n      "@type": "Answer",\n      "text": "REPLACE_WITH_ANSWER"\n    }\n  }]\n}\n</script>'
    elif code_type == "breadcrumb":
        return '<script type="application/ld+json">\n{\n  "@context": "https://schema.org",\n  "@type": "BreadcrumbList",\n  "itemListElement": [{\n    "@type": "ListItem",\n    "position": 1,\n    "name": "Home",\n    "item": "https://' + domain + '"\n  }]\n}\n</script>'
    elif code_type == "product":
        return '<script type="application/ld+json">\n{\n  "@context": "https://schema.org",\n  "@type": "Product",\n  "name": "' + (sample_name or 'REPLACE_WITH_PRODUCT_NAME') + '",\n  "image": "REPLACE_WITH_IMAGE_URL",\n  "description": "REPLACE_WITH_DESCRIPTION",\n  "sku": "REPLACE_WITH_SKU",\n  "offers": {\n    "@type": "Offer",\n    "url": "https://' + domain + '/REPLACE_WITH_PRODUCT_URL",\n    "priceCurrency": "USD",\n    "price": "REPLACE_WITH_PRICE",\n    "availability": "https://schema.org/InStock"\n  }\n}\n</script>'
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
    status, xml, final_url, _ = _fetch_with_retry(f"https://{domain}/sitemap.xml", "sitemap", findings, retries=1)
    
    if status != 200:
        findings["notes"] += f"sitemap_fetch_failed: status={status} url={final_url}. "
    elif not xml or len(xml.strip()) == 0:
        findings["notes"] += "sitemap_empty_response. "

    products, collections, policies = [], [], []

    def parse_locs(xml_text):
        clean_xml = re.sub(r'\sxmlns(:[a-zA-Z0-9]+)?="[^"]+"', '', xml_text)
        clean_xml = re.sub(r'([<\/])[a-zA-Z0-9]+:', r'', clean_xml)
        try:
            root = ET.fromstring(clean_xml)
            return [loc.text for loc in root.findall('.//loc') if loc.text]
        except ET.ParseError:
            # Fallback to bulletproof regex if XML is malformed (e.g., unescaped ampersands)
            return re.findall(r'<loc>(.*?)</loc>', clean_xml, re.IGNORECASE | re.DOTALL)

    if status == 200 and xml:
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

    urls["products"] = products[:3]
    if collections:
        urls["collection"] = collections[0]
    urls["policies_discovered"] = policies

    if not products:
        findings["notes"] += "sitemap_failed_to_yield_products. "

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
                        "description": "llms.txt redirected to a checkout subdomain.",
                        "evidence": f"Final URL: {final_url}",
                        "affected_urls": [final_url],
                        "severity": "medium", "confidence": "high",
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
                        "severity": "high", "confidence": "high",
                        "business_impact": "Prevents generative engines from indexing the brand for conversational commerce.",
                        "difficulty": "Easy",
                        "fix": "Remove blanket Disallow rules for AI user-agents in robots.txt."
                    })
        else:
            if name in ["llms.txt", "agents.md"]:
                score -= 1.0

    if len(blocked_resources) == len(resources):
        findings["dimensions_measured"]["crawlability"] = False
        issues.append({
            "code": "crawlability_unmeasured",
            "description": "All crawlability resources returned bot-challenge pages instead of real content.",
            "evidence": f"Blocked: {', '.join(blocked_resources)}.",
            "affected_urls": list(resources.values()),
            "severity": "medium", "confidence": "low",
            "business_impact": "Crawlability is unknown. The site's WAF may also be blocking legitimate AI crawlers (e.g. GPTBot).",
            "difficulty": "N/A",
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
            "severity": "medium", "confidence": "high",
            "business_impact": "Reduces explicit textual data available for AI systems to resolve pre-purchase customer queries.",
            "difficulty": "Easy",
            "fix": "Publish comprehensive, text-rich policy pages and ensure they are discoverable via navigation or sitemap."
        })

    findings["dimensions"]["answerability"] = max(0, score)
    findings["issues"].extend(issues)
    findings["answerability_matrix"] = {
        "strong_policies": len(found_policies),
        "weak_policies": len(weak_policies)
    }

def _analyze_entities_and_products(domain, sample_urls, findings):
    entity_score = 10.0
    issues = []

    all_nodes = []
    entity_pages_found = 0
    faq_pages_found = 0
    breadcrumb_pages_found = 0
    total_pages_crawled = 0
    csr_pages = 0
    redirect_shell_pages = 0

    urls_to_crawl = [sample_urls["homepage"]]
    if "collection" in sample_urls:
        urls_to_crawl.append(sample_urls["collection"])
    urls_to_crawl.extend(sample_urls.get("products", []))

    for url in urls_to_crawl:
        st, html, final_url, _ = _fetch(url, "crawl", findings)
        if st == 200:
            total_pages_crawled += 1
            nodes = _extract_json_ld(html)
            all_nodes.extend(nodes)

            is_redirect_shell = False
            if final_url and urlparse(final_url).netloc != domain:
                is_redirect_shell = True

            if len(nodes) == 0:
                if is_redirect_shell:
                    redirect_shell_pages += 1
                else:
                    csr_pages += 1

            has_entity = False
            for node in nodes:
                if isinstance(node, dict):
                    t = node.get("@type", "")
                    if isinstance(t, list):
                        t = " ".join(t)
                    if any(x in t for x in ["Organization", "Corporation", "Brand", "WebSite"]):
                        has_entity = True
                    if "FAQPage" in t: faq_pages_found += 1
                    if "BreadcrumbList" in t: breadcrumb_pages_found += 1
            if has_entity:
                entity_pages_found += 1

    if total_pages_crawled > 0:
        if (redirect_shell_pages / total_pages_crawled) > 0.5:
            issues.append({
                "code": "redirect_shell_detected",
                "description": "Core pages redirect to external shells (e.g., checkout subdomains) with no schema.",
                "evidence": f"{redirect_shell_pages}/{total_pages_crawled} pages redirected to external domains without returning schema.",
                "affected_urls": urls_to_crawl,
                "severity": "high", "confidence": "high",
                "business_impact": "AI agents are routed to payment/external domains and blocked before seeing catalog data.",
                "difficulty": "Medium",
                "fix": "Ensure core merchandising URLs resolve on the primary domain without redirecting to checkout/external shells."
            })
        elif (csr_pages / total_pages_crawled) > 0.5:
            issues.append({
                "code": "csr_schema_leak",
                "description": "Client-Side Rendering (CSR) is preventing raw HTML schema extraction.",
                "evidence": f"{csr_pages}/{total_pages_crawled} sampled pages return 0 JSON-LD blocks in raw HTML.",
                "affected_urls": urls_to_crawl,
                "severity": "high", "confidence": "high",
                "business_impact": "Lightweight AI shopping agents that do not execute JavaScript will see 0% entity and product data.",
                "difficulty": "Hard",
                "fix": "Implement Server-Side Rendering (SSR) or Static Site Generation (SSG) for core pages.",
                "fix_snippet": _generate_snippet("organization", domain)
            })

    if total_pages_crawled > 0 and (entity_pages_found / total_pages_crawled) < 0.5:
        entity_score -= 3.0
        issues.append({
            "code": "inconsistent_entity_presence",
            "description": "Brand/Organization schema is missing from more than 50% of sampled pages.",
            "evidence": f"Found on {entity_pages_found}/{total_pages_crawled} sampled pages.",
            "affected_urls": urls_to_crawl,
            "severity": "medium", "confidence": "high",
            "business_impact": "Inconsistent entity mapping makes automated brand reconciliation difficult across the site.",
            "difficulty": "Medium",
            "fix": "Inject global Organization/Brand structured data into the site's master layout template.",
            "fix_snippet": _generate_snippet("organization", domain)
        })

    flat_nodes = []
    for g in all_nodes:
        if isinstance(g, dict):
            if "@graph" in g:
                flat_nodes.extend([n for n in g["@graph"] if isinstance(n, dict)])
            else:
                flat_nodes.append(g)

    has_org, has_same_as = False, False
    for node in flat_nodes:
        t = node.get("@type", "")
        if isinstance(t, list):
            t = " ".join(t)
        if any(x in t for x in ["Organization", "Corporation", "Brand"]):
            has_org = True
            if node.get("sameAs"):
                has_same_as = True

    if not has_org:
        entity_score -= 5.0
        issues.append({
            "code": "missing_organization_entity",
            "description": "Missing Organization/Brand schema in JSON-LD.",
            "evidence": "No Organization, Corporation, or Brand node found across sampled pages.",
            "affected_urls": urls_to_crawl,
            "severity": "high", "confidence": "high",
            "business_impact": "Reduces explicit machine-readable entity clarity for automated systems.",
            "difficulty": "Easy",
            "fix": "Add appropriate Organization/Brand structured data to the site's global template.",
            "fix_snippet": _generate_snippet("organization", domain)
        })
    elif not has_same_as:
        entity_score -= 2.0
        issues.append({
            "code": "weak_entity_trust_chain",
            "description": "Organization exists, but lacks a sameAs trust chain.",
            "evidence": "sameAs array missing or empty.",
            "affected_urls": urls_to_crawl,
            "severity": "medium", "confidence": "high",
            "business_impact": "Knowledge Graph trust score is degraded; automated systems may struggle to disambiguate the brand.",
            "difficulty": "Easy",
            "fix": "Add Wikipedia and official social URLs to the sameAs array."
        })

    findings["dimensions"]["entity_intelligence"] = max(0, entity_score)

    if total_pages_crawled > 0 and faq_pages_found == 0:
        issues.append({
            "code": "missing_faq_schema",
            "description": "No FAQPage schema detected. This reduces direct-citation likelihood in AI answers.",
            "evidence": "0 FAQPage nodes found across sampled pages.",
            "affected_urls": urls_to_crawl,
            "severity": "medium", "confidence": "high",
            "business_impact": "Reduces the probability of the brand's content being cited directly in AI-generated answers.",
            "difficulty": "Easy",
            "fix": "Wrap existing Q&A content in FAQPage schema.",
            "fix_snippet": _generate_snippet("faq", domain)
        })

    if total_pages_crawled > 0 and breadcrumb_pages_found == 0:
        issues.append({
            "code": "missing_breadcrumb_schema",
            "description": "No BreadcrumbList schema detected.",
            "evidence": "0 BreadcrumbList nodes found across sampled pages.",
            "affected_urls": urls_to_crawl,
            "severity": "low", "confidence": "high",
            "business_impact": "AI systems lack explicit hierarchical context for page categorization.",
            "difficulty": "Easy",
            "fix": "Add BreadcrumbList schema to page templates.",
            "fix_snippet": _generate_snippet("breadcrumb", domain)
        })

    products = sample_urls.get("products", [])
    if products:
        product_scores = []
        for p_url in products:
            st, html, final_url, _ = _fetch(p_url, "product", findings)
            if st == 200:
                nodes = _extract_json_ld(html)
                p_score = 0
                has_prod = has_name = has_offers = has_price = has_avail = has_var = has_sku = has_review = False
                for node in nodes:
                    if isinstance(node, dict):
                        t = node.get("@type", "")
                        if isinstance(t, list):
                            t = " ".join(t)
                        if "Product" in t:
                            has_prod = True
                            if node.get("name"): has_name = True
                            if node.get("sku") or node.get("gtin") or node.get("mpn"): has_sku = True
                            if node.get("review") or node.get("aggregateRating"): has_review = True
                            if node.get("offers"):
                                has_offers = True
                                offers = node["offers"]
                                if isinstance(offers, list): offers = offers[0] if offers else {}
                                if isinstance(offers, dict):
                                    if offers.get("price") or offers.get("lowPrice"): has_price = True
                                    if offers.get("availability"): has_avail = True
                            if node.get("hasVariant") or node.get("variants"): has_var = True
                if has_prod: p_score += 20
                if has_name: p_score += 10
                if has_offers: p_score += 15
                if has_price: p_score += 15
                if has_avail: p_score += 15
                if has_var: p_score += 10
                if has_sku: p_score += 5
                if has_review: p_score += 10
                product_scores.append(min(100, p_score))

        avg_prod_score = sum(product_scores) / len(product_scores)
        findings["dimensions"]["product_intelligence"] = avg_prod_score / 10.0
        findings["dimensions_measured"]["product_intelligence"] = True

        if avg_prod_score < 80:
            sample_name = ""
            if product_scores and product_scores[0] > 0: sample_name = "Sample Product"
            issues.append({
                "code": "incomplete_product_schema",
                "description": f"Product schema is {avg_prod_score:.0f}% complete across sampled PDPs.",
                "evidence": f"Sampled {len(products)} products. Missing critical attributes like price, availability, variants, or identifiers.",
                "affected_urls": products,
                "severity": "high", "confidence": "high",
                "business_impact": "Automated shopping agents cannot verify stock, cost, or specific SKUs, leading to abandoned machine-checkouts.",
                "difficulty": "Medium",
                "fix": "Map inventory, pricing, variants, and SKUs to the Product schema properties.",
                "fix_snippet": _generate_snippet("product", domain, sample_name)
            })
    else:
        findings["dimensions_measured"]["product_intelligence"] = False
        issues.append({
            "code": "product_intelligence_unmeasured",
            "description": "No product pages could be sampled.",
            "evidence": findings["notes"],
            "affected_urls": [],
            "severity": "medium", "confidence": "low",
            "business_impact": "Product schema quality is unknown.",
            "difficulty": "N/A",
            "fix": "Re-run the audit, or manually verify Product schema."
        })

    findings["issues"].extend(issues)

def _check_agentic_commerce(domain, findings):
    capabilities = {"Discovery": "FAIL", "UCP": "FAIL", "MCP": "FAIL", "Catalog": "FAIL", "Cart/Checkout": "FAIL"}
    score = 0.0

    st_ucp, ucp_body, final_url, _ = _fetch(f"https://{domain}/.well-known/ucp", "ucp", findings)
    if st_ucp == 200:
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
        capabilities["MCP"] = "PASS"
        score += 2.0
        try:
            payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
            headers = {"Content-Type": "application/json", "Accept": "application/json"}
            if USE_STEALTH:
                r = cffi_requests.post(mcp_endpoint, json=payload, headers=headers, timeout=TIMEOUT, impersonate="chrome120")
            else:
                r = std_requests.post(mcp_endpoint, json=payload, headers=headers, timeout=TIMEOUT)

            if r.status_code == 200:
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
                    "severity": "high", "confidence": "high",
                    "business_impact": "Agentic checkout pipes are broken. AI agents cannot transact.",
                    "difficulty": "Hard",
                    "fix": "Debug MCP server routing and ensure public JSON-RPC access."
                })
        except Exception as e:
            findings["notes"] += f"MCP exception: {e}. "

    findings["dimensions"]["agentic_commerce"] = score
    findings["agentic_capabilities"] = capabilities
    
    if capabilities["UCP"] == "PASS" and (capabilities["Catalog"] == "FAIL" or capabilities["Cart/Checkout"] == "FAIL"):
        findings["issues"].append({
            "code": "agentic_commerce_partial",
            "description": "UCP discovery file exists, but the MCP tool handshake for Catalog/Cart failed.",
            "evidence": f"Capabilities: {capabilities}",
            "affected_urls": [f"https://{domain}/.well-known/ucp"],
            "severity": "medium", "confidence": "high",
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
        }
    }

    if not _check_domain_reachable(domain, findings):
        findings["overall_geo_score"] = None
        findings["score_confidence"] = "unreachable"
        findings["issues"] = [{
            "code": "domain_unreachable",
            "description": f"{domain} did not respond to any request - ikely wrong domain, DNS failure, or site offline.",
            "evidence": findings["notes"],
            "affected_urls": [],
            "severity": "high", "confidence": "high",
            "business_impact": "Cannot audit a site that cannot be reached.",
            "difficulty": "N/A",
            "fix": "Verify the domain is correct and the site is live before re-running.",
        }]
        return findings

    sample_urls = _sample_urls(domain, findings)

    _check_crawlability(domain, findings)
    _check_answerability(domain, sample_urls, findings)
    _analyze_entities_and_products(domain, sample_urls, findings)
    _check_agentic_commerce(domain, findings)

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
        # Calculate score based only on measured dimensions
        measured_score = sum(dims[k] * active_weights[k] for k in active_weights) / weight_total
        
        # Fix 2: Penalize overall score if significant dimensions are unmeasured
        confidence_ratio = weight_total / total_possible_weight
        overall = measured_score * confidence_ratio

    findings["overall_geo_score"] = round(overall, 1)
    findings["score_confidence"] = (
        "full" if weight_total == sum(WEIGHTS.values()) else "partial"
    )

    if dims.get("entity_intelligence") is not None and dims["entity_intelligence"] < 8:
        findings["business_interpretation"].append("The site lacks consistent, machine-readable brand identity mapping, which may introduce retrieval dependencies for AI engines.")
    if dims.get("product_intelligence") is not None and dims["product_intelligence"] < 8:
        findings["business_interpretation"].append("Incomplete product data structures may prevent autonomous agents from verifying inventory and executing transactions.")
    if dims.get("agentic_commerce") is not None and dims["agentic_commerce"] < 10:
        findings["business_interpretation"].append("The infrastructure does not fully support standardized agentic commerce protocols, limiting compatibility with next-generation shopping agents.")

    return findings

def geo_opportunity_score(geo_findings: dict) -> int:
    return int(geo_findings.get("overall_geo_score", 0))