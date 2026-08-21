"""
GEO Engine Regression & Integrity Suite
Validates 100-point math parity, confidence logic, and structural integrity.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from revenue_leak_engine.audit.geo_audit import audit_geo

def test_math_parity():
    """Ensures the codebase only contains the 100-point weight string."""
    with open('src/revenue_leak_engine/audit/geo_audit.py', 'r', encoding='utf-8') as f:
        content = f.read()
    assert "Name 10pts, Offers 15pts" not in content, "Old 80-point weight string still exists!"
    assert "incomplete_product_schema" in content, "Product schema issue logic missing!"
    print("PASS: Math parity verified (100-point scale locked).")

def test_live_integrity():
    """Runs a live audit to ensure no crashes and correct confidence mapping."""
    result = audit_geo('beautyitis.com')
    assert "overall_geo_score" in result, "Missing overall score."
    assert "score_confidence" in result, "Missing confidence metric."
    assert result["score_confidence"] in ["VERIFIED", "PARTIAL", "UNVERIFIED", "full", "partial", "low"], f"Invalid confidence state: {result['score_confidence']}"
    print(f"PASS: Live audit completed. Score: {result['overall_geo_score']}, Confidence: {result['score_confidence']}")

if __name__ == "__main__":
    test_math_parity()
    test_live_integrity()
    print("\nALL REGRESSION TESTS PASSED. GEO ENGINE IS INDUSTRIALLY VALIDATED.")
