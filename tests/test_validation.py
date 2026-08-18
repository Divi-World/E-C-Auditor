"""
False-positive / false-negative validation suite.
Proves the industrial auditor can be trusted.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from revenue_leak_engine.audit.geo_audit import _extract_json_ld, _analyze_graph

def test_nested_graph_pass():
    """Partner Rule: Organization in @graph -> PASS"""
    html = '''<script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@graph": [
        {
          "@type": "Organization",
          "@id": "https://brand.com/#org",
          "name": "Brand",
          "sameAs": ["https://twitter.com/brand"]
        }
      ]
    }
    </script>'''
    graphs = _extract_json_ld(html)
    findings = {"issues": [], "notes": ""}
    _analyze_graph("brand.com", graphs, findings, ["homepage"])
    
    # Assert no missing_organization_entity issue exists
    codes = [i["code"] for i in findings["issues"]]
    assert "missing_organization_entity" not in codes, "FAIL: Auditor missed nested @graph Organization"
    assert "weak_entity_trust_chain" not in codes, "FAIL: Auditor missed sameAs in nested @graph"
    print("[OK] TEST PASSED: Nested @graph & sameAs trust chain correctly validated.")

if __name__ == "__main__":
    test_nested_graph_pass()
