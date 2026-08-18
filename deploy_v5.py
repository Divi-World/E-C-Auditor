import os

code = """
import re
import json
import xml.etree.ElementTree as ET
import requests as std_requests
from urllib.parse import urlparse

try:
    from curl_cffi import requests as cffi_requests
    USE_STEALTH = True
except ImportError:
    USE_STEALTH = False

TIMEOUT = 10
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; RevenueLeakEngine/5.0-Enterprise)"}

def _fetch(url, notes_key, findings):
    try:
        if USE_STEALTH:
            r = cffi_requests.get(url, timeout=TIMEOUT, impersonate="chrome120", allow_redirects=True)
        else:
            r = std_requests.get(url, timeout=TIMEOUT, headers=HEADERS, allow_redirects=True)
        return r.status_code, r.text, str(r.url), r.headers.get('content-type', '')
    except Exception as e:
        findings["notes"] += f"{notes_key}: {type(e).__name__}. "
        return None, "", "", ""

def _extract_json_ld(html):
    blocks = re.findall(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.DOTALL | re.I)
    parsed = []
    for block in blocks:
        block = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', block, flags=re.DOTALL)
        try: parsed.append(json.loads(block))
        except: continue
    return parsed

def _sample_urls(domain, findings):
    urls = {"homepage": f"https://{domain}/"}
    status, xml, _, _ = _fetch(f"https://{domain}/sitemap.xml", "sitemap", findings)
    if status == 200 and "<urlset" in xml:
        try:
            clean_xml = re.sub(r'\sxmlns="[^"]+"', '', xml, count=1)
            root = ET.fromstring(clean_xml)
            locs = [loc.text for loc in root.findall('.//loc') if loc.text]
            products, collections, policies = [], [], []
            for loc in locs:
                if "/products/" in loc and "/collections/" not in loc: products.append(loc)
                elif "/collections/" in loc and not loc.endswith("/collections"): collections.append(loc)
                elif "/policies/" in loc or "/pages/shipping" in loc or "/pages/returns" in loc or "/pages/faq" in loc: policies.append(loc)
            
            urls["products"] = products[:3]
            if collections: urls["collection"] = collections[0]
            for p in policies:
                if "shipping" in p: urls["shipping"] = p
                elif "return" in p or "refund" in p: urls["returns"] = p
                elif "faq" in p: urls["faq"] = p
        except: findings["notes"] += "sitemap parse error. "
    return urls

def audit_geo(domain: str) -> dict:
    findings = {
        "domain": domain, 
        "issues": [], 
        "notes": "", 
        "dimensions": {
            "crawlability": 10.0,
            "entity_intelligence": 10.0,
            "product_intelligence": 10.0,
            "answerability": 10.0,
            "agentic_commerce": 10.0
        }
    }
    
    sample_urls = _sample_urls(domain, findings)
    all_nodes = []
    pages_crawled = []
    
    st, html, _, _ = _fetch(sample_urls["homepage"], "homepage", findings)
    if st == 200: all_nodes.extend(_extract_json_ld(html)); pages_crawled.append("homepage")
    
    if "collection" in sample_urls:
        st, html, _, _ = _fetch(sample_urls["collection"], "collection", findings)
        if st == 200: all_nodes.extend(_extract_json_ld(html)); pages_crawled.append("collection")
        
    policy_hits = 0
    for p_type in ["shipping", "returns", "faq"]:
        if p_type in sample_urls:
            st, html, url, _ = _fetch(sample_urls[p_type], p_type, findings)
            if st == 200: 
                all_nodes.extend(_extract_json_ld(html))
                pages_crawled.append(p_type)
                policy_hits += 1
                
    if policy_hits < 2:
        findings["dimensions"]["answerability"] -= 4.0
        findings["issues"].append({
            "code": "missing_policy_pages",
            "description": "Missing explicit Shipping, Returns, or FAQ pages.",
            "evidence": f"Found {policy_hits}/3 core policy pages in sitemap.",
            "severity": "medium", "confidence": "high",
            "business_impact": "Reduces the explicit textual data available for AI systems to answer commercial customer queries.",
            "difficulty": "Easy", "fix": "Ensure core policy pages are published and linked in the sitemap."
        })

    products = sample_urls.get("products", [])
    product_scores = []
    for p_url in products:
        st, html, _, _ = _fetch(p_url, "product", findings)
        if st == 200:
            pages_crawled.append("product")
            nodes = _extract_json_ld(html)
            all_nodes.extend(nodes)
            
            p_score = 0
            has_prod, has_name, has_offers, has_price, has_avail, has_var = False, False, False, False, False, False
            for node in nodes:
                if isinstance(node, dict):
                    t = node.get("@type", "")
                    if isinstance(t, list): t = " ".join(t)
                    if "Product" in t:
                        has_prod = True
                        if node.get("name"): has_name = True
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
            if has_offers: p_score += 20
            if has_price: p_score += 20
            if has_avail: p_score += 20
            if has_var: p_score += 10
            product_scores.append(p_score)

    if products:
        avg_prod_score = sum(product_scores) / len(product_scores)
        findings["dimensions"]["product_intelligence"] = avg_prod_score / 10.0
        
        if avg_prod_score < 80:
            findings["issues"].append({
                "code": "incomplete_product_schema",
                "description": f"Product schema is {avg_prod_score:.0f}% complete across sampled PDPs.",
                "evidence": f"Sampled {len(products)} products. Missing critical attributes like price, availability, or variants.",
                "severity": "high", "confidence": "high",
                "business_impact": "Automated shopping agents cannot verify stock or cost, leading to abandoned machine-checkouts.",
                "difficulty": "Medium", "fix": "Map inventory, pricing, and variant variables to the Product 'offers' and 'hasVariant' schema properties."
            })

    has_org, has_same_as = False, False
    for node in all_nodes:
        if isinstance(node, dict):
            t = node.get("@type", "")
            if isinstance(t, list): t = " ".join(t)
            if "Organization" in t or "Corporation" in t or "Brand" in t:
                has_org = True
                if node.get("sameAs"): has_same_as = True

    if not has_org:
        findings["dimensions"]["entity_intelligence"] -= 6.0
        findings["issues"].append({
            "code": "missing_organization_entity",
            "description": "Missing Organization/Brand schema in JSON-LD.",
            "evidence": "No Organization, Corporation, or Brand node found across sampled pages.",
            "severity": "high", "confidence": "high",
            "business_impact": "Reduces explicit machine-readable entity clarity, making brand reconciliation harder for automated systems.",
            "difficulty": "Easy", "fix": "Add Organization schema to the global layout/theme.liquid."
        })
    elif not has_same_as:
        findings["dimensions"]["entity_intelligence"] -= 3.0
        findings["issues"].append({
            "code": "weak_entity_trust_chain",
            "description": "Organization exists, but lacks a sameAs trust chain.",
            "evidence": "sameAs array missing or empty.",
            "severity": "medium", "confidence": "high",
            "business_impact": "Knowledge Graph trust score is degraded; automated systems may struggle to disambiguate the brand.",
            "difficulty": "Easy", "fix": "Add Wikipedia and official social URLs to the sameAs array."
        })

    st_llms, _, final_llms, ct_llms = _fetch(f"https://{domain}/llms.txt", "llms.txt", findings)
    if st_llms != 200 or ("text/plain" not in ct_llms and "text/markdown" not in ct_llms):
        findings["dimensions"]["crawlability"] -= 4.0
        findings["issues"].append({
            "code": "invalid_llms_txt",
            "description": "llms.txt is missing, blocked, or malformed.",
            "evidence": f"Status: {st_llms}, Content-Type: {ct_llms}",
            "severity": "medium", "confidence": "high",
            "business_impact": "AI crawlers lack a standardized map of the site's context.",
            "difficulty": "Easy", "fix": "Publish a valid text/markdown llms.txt file at the domain root."
        })
    else:
        parsed_final = urlparse(final_llms or "")
        if parsed_final.netloc.lower() != domain and "checkout" in parsed_final.netloc.lower():
            findings["dimensions"]["crawlability"] -= 2.0
            findings["issues"].append({
                "code": "llms_txt_checkout_routing",
                "description": "llms.txt redirected to a checkout subdomain.",
                "evidence": f"Final URL: {final_llms}",
                "severity": "medium", "confidence": "high",
                "business_impact": "AI agents hitting WAF-protected checkout domains may be blocked before seeing the catalog.",
                "difficulty": "Medium", "fix": "Host llms.txt on the primary brand CDN."
            })

    st_ucp, ucp_body, _, _ = _fetch(f"https://{domain}/.well-known/ucp", "ucp", findings)
    mcp_endpoint = None
    if st_ucp == 200:
        try:
            data = json.loads(ucp_body)
            for svc_list in data.get("ucp", {}).get("services", {}).values():
                if isinstance(svc_list, list):
                    for svc in svc_list:
                        if "endpoint" in svc: mcp_endpoint = svc["endpoint"]
        except: pass

    agentic_score = 0
    if st_ucp == 200: agentic_score += 20
    if mcp_endpoint: agentic_score += 20
    
    if mcp_endpoint:
        try:
            payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
            headers = {"Content-Type": "application/json", "Accept": "application/json"}
            if USE_STEALTH:
                r = cffi_requests.post(mcp_endpoint, json=payload, headers=headers, timeout=TIMEOUT, impersonate="chrome120")
            else:
                r = std_requests.post(mcp_endpoint, json=payload, headers=headers, timeout=TIMEOUT)
            
            if r.status_code == 200:
                agentic_score += 20
                data = json.loads(r.text)
                tools = {t.get("name", "").lower() for t in data.get("result", {}).get("tools", [])}
                if any("search" in t or "catalog" in t for t in tools): agentic_score += 20
                if any("cart" in t or "checkout" in t for t in tools): agentic_score += 20
                findings["notes"] += f"Agentic Commerce Readiness: {agentic_score/10:.1f}/10. "
            else:
                findings["dimensions"]["agentic_commerce"] = agentic_score / 10.0
                findings["issues"].append({
                    "code": "mcp_handshake_failed",
                    "description": "MCP endpoint returned error during JSON-RPC handshake.",
                    "evidence": f"POST {mcp_endpoint} -> {r.status_code}",
                    "severity": "high", "confidence": "high",
                    "business_impact": "Agentic checkout pipes are broken. AI agents cannot transact.",
                    "difficulty": "Hard", "fix": "Debug MCP server routing and ensure public JSON-RPC access."
                })
        except Exception as e:
            findings["notes"] += f"MCP exception: {e}. "
            
    findings["dimensions"]["agentic_commerce"] = agentic_score / 10.0

    dims = findings["dimensions"]
    overall = sum(dims.values()) / len(dims)
    findings["overall_geo_score"] = round(overall, 1)
    
    return findings

def geo_opportunity_score(geo_findings: dict) -> int:
    return int(geo_findings.get("overall_geo_score", 0))
"""

with open('src/revenue_leak_engine/audit/geo_audit.py', 'w', encoding='utf-8') as f:
    f.write(code)
print('v5 Enterprise Auditor deployed successfully.')
