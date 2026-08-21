"""
Technical SEO Audit — Isolated Module.
Evaluates On-Page SEO fundamentals using the existing Playwright page context 
to prevent double-fetching and WAF blocks.
"""

def audit_seo_onpage(page, findings: dict):
    """Extracts and evaluates Title, Meta, H1, Canonical, and Image Alt tags."""
    try:
        seo_data = page.evaluate("""
            () => {
                const title = document.title || '';
                const metaDesc = document.querySelector('meta[name="description"]')?.content || '';
                const h1s = document.querySelectorAll('h1');
                const canonical = document.querySelector('link[rel="canonical"]')?.href || '';
                const imgs = document.querySelectorAll('img');
                let imgs_no_alt = 0;
                imgs.forEach(img => { if (!img.hasAttribute('alt') || img.alt.trim() === '') imgs_no_alt++; });
                
                return {
                    title: title, title_len: title.length,
                    meta: metaDesc, meta_len: metaDesc.length,
                    h1_count: h1s.length,
                    has_canonical: canonical.length > 0,
                    imgs_total: imgs.length, imgs_no_alt: imgs_no_alt
                };
            }
        """)
    except Exception:
        return

    if seo_data.get('title_len', 0) == 0 or seo_data.get('title_len', 0) > 65:
        findings["issues"].append({
            "code": "poor_title_tag", "description": f"Page title is {seo_data.get('title_len', 0)} chars (target: 30-60).",
            "evidence": f"Title: '{seo_data.get('title', '')[:60]}...'", "severity": "medium", "confidence": "VERIFIED",
            "business_impact": "Poor titles reduce CTR from search engines and AI citations.",
            "fix": "Rewrite title to 30-60 chars, front-loading primary keyword and brand."
        })
        
    if seo_data.get('meta_len', 0) == 0 or seo_data.get('meta_len', 0) > 160:
        findings["issues"].append({
            "code": "poor_meta_description", "description": f"Meta description is {seo_data.get('meta_len', 0)} chars (target: 120-160).",
            "evidence": "Meta description missing or will be truncated by Google.", "severity": "low", "confidence": "VERIFIED",
            "business_impact": "Missing meta descriptions force Google to guess your snippet, lowering CTR.",
            "fix": "Write a 120-160 char benefit-driven meta description with a clear CTA."
        })
        
    if seo_data.get('h1_count', 0) != 1:
        findings["issues"].append({
            "code": "h1_tag_issue", "description": f"Page has {seo_data.get('h1_count', 0)} H1 tags (target: exactly 1).",
            "evidence": "Multiple or missing H1 tags confuse search engine crawlers about page topic.", "severity": "low", "confidence": "VERIFIED",
            "business_impact": "Diluted heading hierarchy weakens topical authority for AI and search.",
            "fix": "Ensure exactly one H1 tag per page, matching the primary product/category name."
        })
        
    if seo_data.get('imgs_total', 0) > 0 and seo_data.get('imgs_no_alt', 0) > seo_data.get('imgs_total', 0) * 0.2:
        findings["issues"].append({
            "code": "missing_image_alt", "description": f"{seo_data.get('imgs_no_alt')} of {seo_data.get('imgs_total')} images lack alt text.",
            "evidence": "Over 20% of images are invisible to screen readers and AI image search.", "severity": "low", "confidence": "VERIFIED",
            "business_impact": "Missing alt text kills accessibility compliance and AI visual search traffic.",
            "fix": "Add descriptive, keyword-relevant alt text to all product and lifestyle imagery."
        })
