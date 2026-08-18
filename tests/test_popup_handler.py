from revenue_leak_engine.audit.popup_handler import classify_overlay


def test_classify_cookie_banner_is_not_a_leak():
    info = {"id": "cookie-banner", "cls": "consent-bar",
            "text": "We use cookies to improve your experience. Accept All"}
    assert classify_overlay(info) == "cookie_consent"


def test_classify_discount_quiz_popup_is_marketing():
    # The exact cocokind overlay from our first live run
    info = {"id": "", "cls": "newsletter-modal",
            "text": "unlock 10% off plus get early access to launches "
                    "What are you shopping for today? SERUMS MOISTURIZERS"}
    assert classify_overlay(info) == "marketing_popup"


def test_classify_unknown_overlay():
    info = {"id": "", "cls": "something-new", "text": "hello world"}
    assert classify_overlay(info) == "generic_overlay"


def test_classify_privacy_bottom_sheet_thenueco_style():
    info = {"id": "", "cls": "cookie-banner",
            "text": "We care about your privacy We use cookies and similar "
                    "technologies Ok - that's fine No Manage preferences"}
    assert classify_overlay(info) == "cookie_consent"


def test_classify_region_gate():
    info = {"id": "", "cls": "country-modal",
            "text": "Choose your country United States Canada United Kingdom"}
    assert classify_overlay(info) == "region_gate"


def test_classify_age_gate():
    info = {"id": "", "cls": "age-verify", "text": "Are you over 21 years old? Yes No"}
    assert classify_overlay(info) == "age_gate"