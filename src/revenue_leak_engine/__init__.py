"""Revenue Leak Engine — Shopify audit and client acquisition pipeline.

Public API re-exported here so callers can do:

    from revenue_leak_engine import find_advertiser_domains, is_shopify, audit_site
"""
from .discovery.meta_ads_search import find_advertiser_domains
from .qualification.shopify_detect import is_shopify
from .audit.site_audit import audit_site
from .reporting.report_generator import generate_report, opportunity_score
from .outreach.outreach_draft import draft_email

__all__ = [
    "find_advertiser_domains",
    "is_shopify",
    "audit_site",
    "generate_report",
    "opportunity_score",
    "draft_email",
]

__version__ = "0.2.0"
