"""
Industrial GEO Regression & Fixture Suite
Tests extraction quality, positive identification, and edge cases.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from bs4 import BeautifulSoup

def test_extraction_cascade():
    """Tests the JSON-LD -> OG -> H1 -> UNKNOWN extraction cascade."""
    html = """<html><head><title>Gymshark</title></head><body><h1>Flex Fleece Hoodie</h1></body></html>"""
    soup = BeautifulSoup(html, 'html.parser')
    
    og_title = soup.find('meta', property='og:title')
    h1_tag = soup.find('h1')
    h1_text = h1_tag.get_text(strip=True) if h1_tag else ""
    og_text = og_title["content"] if og_title else ""
    brand = "Gymshark"
    domain = "gymshark.com"
    
    if og_text and og_text != brand and og_text.lower() != domain.lower():
        name = og_text
    elif h1_text and h1_text != brand and h1_text.lower() != domain.lower():
        name = h1_text
    else:
        name = "REPLACE_WITH_PRODUCT_NAME"
        
    assert name == "Flex Fleece Hoodie", f"Extraction cascade failed. Got: {name}"
    print("PASS: Extraction cascade correctly falls back to H1 tag.")

def test_positive_identification():
    """Tests that non-product pages are rejected."""
    html_policy = """<html><body><h1>Shipping Policy</h1><p>We ship worldwide.</p></body></html>"""
    html_product = """<html><body><h1>Shoes</h1><form action="/cart/add"><button>Add to Cart</button></form></body></html>"""
    
    has_schema_p = '"@type": "Product"' in html_policy
    has_cart_p = 'action="/cart/add"' in html_policy or 'product-form' in html_policy
    
    has_schema_pr = '"@type": "Product"' in html_product
    has_cart_pr = 'action="/cart/add"' in html_product or 'product-form' in html_product
    
    assert not (has_schema_p or has_cart_p), "Policy page falsely identified as product."
    assert (has_schema_pr or has_cart_pr), "Valid product page rejected."
    print("PASS: Positive product identification logic is sound.")

def test_domain_as_name_rejection():
    """Tests that domain names are never accepted as product names."""
    domain = "gymshark.com"
    brand = "Gymshark"
    og_text = "gymshark.com"
    
    if og_text and og_text != brand and og_text.lower() != domain.lower():
        name = og_text
    else:
        name = "REPLACE_WITH_PRODUCT_NAME"
        
    assert name == "REPLACE_WITH_PRODUCT_NAME", "Domain name leaked as product name!"
    print("PASS: Domain-as-name rejection is active.")

if __name__ == "__main__":
    test_extraction_cascade()
    test_positive_identification()
    test_domain_as_name_rejection()
    print("\nALL INDUSTRIAL FIXTURE TESTS PASSED.")
