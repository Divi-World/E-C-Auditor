from revenue_leak_engine.qualification.shopify_detect import normalize_domain


def test_normalize_strips_protocol_and_www():
    assert normalize_domain("https://www.brand.com/") == "brand.com"
    assert normalize_domain("http://brand.com") == "brand.com"
    assert normalize_domain("brand.com") == "brand.com"


def test_normalize_lowercases_and_trims():
    assert normalize_domain("  Brand.COM  ") == "brand.com"
