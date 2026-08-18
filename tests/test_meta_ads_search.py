from revenue_leak_engine.discovery.meta_ads_search import (
    _root_domain, _unwrap_facebook_redirect, _extract_candidate_links,
)


def test_root_domain_collapses_subdomains():
    assert _root_domain("shop.brand.com") == "brand.com"
    assert _root_domain("brand.com") == "brand.com"


def test_root_domain_handles_multi_part_tlds():
    assert _root_domain("brand.co.uk") == "brand.co.uk"
    assert _root_domain("shop.brand.co.uk") == "brand.co.uk"


def test_unwrap_facebook_redirect_extracts_real_url():
    wrapped = "https://l.facebook.com/l.php?u=https%3A%2F%2Fbrand.com%2Fproducts%2Fserum%3Ffbclid%3Dabc"
    result = _unwrap_facebook_redirect(wrapped)
    assert result.startswith("https://brand.com/products/serum")


def test_unwrap_facebook_redirect_passthrough_for_normal_urls():
    normal = "https://brand.com/products/serum"
    assert _unwrap_facebook_redirect(normal) == normal


def test_extract_candidate_links_prioritizes_og_url():
    html = """
    <html><head>
    <meta property="og:url" content="https://brand.com/products/serum">
    </head><body>
    <a href="https://facebook.com/brandpage">Brand Page</a>
    <a href="https://brand.com/products/serum">Shop Now</a>
    </body></html>
    """
    candidates = _extract_candidate_links(html)
    assert candidates[0] == "https://brand.com/products/serum"


def test_extract_candidate_links_falls_back_to_cta_links():
    html = """
    <html><body>
    <a href="https://facebook.com/brandpage">Brand Page</a>
    <a href="https://brand.com/collections/all">Shop Now</a>
    </body></html>
    """
    candidates = _extract_candidate_links(html)
    assert "https://brand.com/collections/all" in candidates
