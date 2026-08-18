import re

with open('src/revenue_leak_engine/audit/geo_audit.py', 'r', encoding='utf-8') as f:
    content = f.read()

new_sample_urls = '''def _sample_urls(domain, findings):
    urls = {"homepage": f"https://{domain}/"}
    status, xml, final_url, _ = _fetch_with_retry(f"https://{domain}/sitemap.xml", "sitemap", findings, retries=1)
    
    # DIAGNOSTIC TRAIL: Log non-200 or empty sitemaps
    if status != 200:
        findings["notes"] += f"sitemap_fetch_failed: status={status} url={final_url}. "
    elif not xml or len(xml.strip()) == 0:
        findings["notes"] += "sitemap_empty_response. "

    products, collections, policies = [], [], []
    sitemap_parsed_successfully = False

    if status == 200 and xml:
        if "<urlset" in xml or "<sitemapindex" in xml:
            try:
                # BULLETPROOF XML CLEANING: Strip ALL xmlns declarations AND tag prefixes
                clean_xml = re.sub(r'\\sxmlns(:[a-zA-Z0-9]+)?="[^"]+"', '', xml)
                clean_xml = re.sub(r'([<\\\\/])[a-zA-Z0-9]+:', r'\\1', clean_xml)
                
                root = ET.fromstring(clean_xml)
                locs = [loc.text for loc in root.findall('.//loc') if loc.text]
                
                if not locs:
                    findings["notes"] += f"sitemap_no_locs_found: len={len(xml)}. "
                    
                for loc in locs:
                    loc = _ensure_primary_domain(loc, domain)
                    if "products" in loc.lower() or "product" in loc.lower():
                        if "collections" not in loc and "categories" not in loc:
                            products.append(loc)
                    elif "collections" in loc.lower() or "categories" in loc.lower():
                        if not loc.endswith("/collections") and not loc.endswith("/categories"):
                            collections.append(loc)
                    elif any(p in loc.lower() for p in ["/policies/", "/pages/shipping", "/pages/returns", "/pages/faq", "/pages/contact"]):
                        policies.append(loc)
                sitemap_parsed_successfully = True
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
                if any(p in link.lower() for p in ["shipping", "return", "refund", "faq", "contact"]):
                    if link not in policies:
                        policies.append(link)
                        if len(policies) >= 4:
                            break

    urls["products"] = products[:3]
    if collections:
        urls["collection"] = collections[0]
    urls["policies_discovered"] = policies

    # FINAL DIAGNOSTIC TRAIL
    if not products:
        findings["notes"] += "sitemap_failed_to_yield_products. "

    return urls
'''

pattern = re.compile(r'def _sample_urls\(domain, findings\):.*?return urls\n', re.DOTALL)
new_content = pattern.sub(new_sample_urls, content)

if new_content == content:
    print("ERROR: Could not find _sample_urls to replace.")
else:
    with open('src/revenue_leak_engine/audit/geo_audit.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("SUCCESS: _sample_urls patched with Bulletproof XML parser and Diagnostic Trail.")
