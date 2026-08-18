from revenue_leak_engine.reporting.report_generator import generate_report, opportunity_score


def _findings(issues):
    return {
        "domain": "testbrand.com",
        "product_url": "https://testbrand.com/products/serum",
        "load_time_ms": 5200,
        "issues": issues,
    }


def test_opportunity_score_weights_by_severity():
    findings = _findings([
        {"code": "slow_load", "severity": "high", "description": "", "evidence": ""},
        {"code": "no_express_checkout", "severity": "medium", "description": "", "evidence": ""},
        {"code": "no_review_widget", "severity": "low", "description": "", "evidence": ""},
    ])
    # 3 (high) + 2 (medium) + 1 (low) = 6
    assert opportunity_score(findings) == 6


def test_opportunity_score_caps_at_ten():
    findings = _findings([
        {"code": "slow_load", "severity": "high", "description": "", "evidence": ""}
        for _ in range(5)
    ])
    assert opportunity_score(findings) == 10


def test_opportunity_score_zero_for_no_issues():
    assert opportunity_score(_findings([])) == 0


def test_generate_report_writes_html_file(tmp_path, monkeypatch):
    import revenue_leak_engine.reporting.report_generator as rg
    monkeypatch.setattr(rg, "REPORTS_DIR", tmp_path)

    findings = _findings([
        {"code": "slow_load", "severity": "high",
         "description": "Slow load.", "evidence": "5200ms"},
    ])
    path = generate_report(findings)
    content = open(path, encoding="utf-8").read()

    assert "testbrand.com" in content
    assert "Slow load." in content
    assert "Opportunity score: 3/10" in content
