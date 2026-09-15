# REVENUE LEAK ENGINE: TOP 1 GLOBAL GEO ROADMAP (LOCK: 90526)

## PHASE 1: CREDIBILITY & STABILITY (Must Fix Before Outreach)
1. **Fix GEO Confidence Badge Wiring**: Map `score_confidence` from `geo_audit.py` to the GEO template render call.
2. **Fix Entity Density Denominator**: Use visible text length (strip scripts/styles) instead of raw HTML length.
3. **Eradicate Hardcoded Global Claims**: Replace "12.4%" and "1.8x" with site-specific measured gaps.
4. **Relabel Niche Benchmarks**: Change "Industry Avg" to "Reference Threshold".
5. **Audit Business Interpretation**: Ensure all executive summary sentences are conditionally true.

## PHASE 2: HIGH-VALUE E-COMMERCE DIFFERENTIATION
6. **Revenue-at-Risk Layer**: Convert schema/orphan gaps into commercial risk tiers.
7. **Historical Score Storage**: Add SQLite table for domain/timestamp/scores.
8. **Competitive Angle**: Enrich outreach with paid search vs. schema gap data.

## PHASE 3: TRUE GEO MONITORING PRODUCT (Future Scope)
9. **Live LLM Citation Tests**: Real prompts parsed for brand mentions.
10. **Competitor Share-of-Voice**: Track brand vs competitor mentions.
11. **Dashboard & Trends**: Visualize historical improvements.





❌ WHAT IS REMAINING (The Final Frontier)
Live LLM Citation Tests (Roadmap Phase 3.1): FAILING. The architecture is built, but the SQLite insert is returning 0 rows. We must fix the database connection/path issue in the tracker module.
Competitor Share-of-Voice (Roadmap Phase 3.2): PENDING. Depends on the LLM tracker fix. Needs to parse actual API responses to calculate market share.
Dashboard & Trends (Roadmap Phase 3.3 / Phase 4): PENDING. Visualizing the geo_history and citation_history data into a client-facing retention dashboard.
Autonomous PR Generation (Phase 4): PENDING. Packaging the fix_snippet into a standardized GitHub/GitLab Pull Request JSON payload.
Industrial Comparison: Us vs. The Giants
Vs. Sitebulb/Lumar: They win on visual crawl maps and JS rendering at scale. We win on e-commerce-specific GEO interpretation, AI crawler rules, and platform-native implementation guidance.
Vs. Profound/SchemaApp: They win on live LLM visibility tracking (Share-of-Voice). We win on technical e-commerce remediation, schema fix generation, and revenue leak framing.
The Gap: To beat Profound, we must fix the Live LLM Citation Tracker (Phase 3.1) so we can prove actual brand mentions in AI outputs.