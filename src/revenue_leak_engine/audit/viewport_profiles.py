"""
Viewport Profiles for Multi-Device Telemetry.
Isolates hardware configurations to prevent core audit logic corruption.
"""

MOBILE_PROFILE = {
    "name": "mobile",
    "viewport": {"width": 390, "height": 844},
    "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "has_touch": True,
    "is_mobile": True
}

DESKTOP_PROFILE = {
    "name": "desktop",
    "viewport": {"width": 1920, "height": 1080},
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "has_touch": False,
    "is_mobile": False
}

PROFILES = [MOBILE_PROFILE, DESKTOP_PROFILE]
