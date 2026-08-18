# Revenue Leak Engine — Roadmap

## 0. What this replaces

This project roadmap covers sequenced
six separate "engines" (discovery, enrichment, audit, scoring, reporting,
outreach). The business risk isn't "can we detect leaks at scale," it's "can we close one
client." This roadmap is sequenced so real, qualified leads exist within
days, and automation is added only where it removes a proven bottleneck.

Same engineering principles as before — they're worth keeping:
- evidence before claims
- human review before any outreach
- suppression list respected, always
- no fabricated verification
- no mass spam, ever

## 1. Product identity

**What it is:** an internal lead-intelligence and audit tool that finds
Shopify beauty/skincare brands already running paid ads, audits their
mobile product pages for conversion leaks, and produces evidence-based
reports + outreach drafts to support selling CRO, design, PPC, and SEO
services.

**What it is not:** a SaaS product sold to end users. This is sales-ops
tooling for a service business. Revenue scales with your delivery
capacity (audits, sprints, retainers), not with software users. Know
which business model you're in — see §7 for what that means for pricing
and time allocation.

**North star:** every report that goes out is something a founder can
read in two minutes and think "yeah, that's costing me money" — backed by
a screenshot, not a guess.

## 2. Locked strategic decisions

| Decision | Choice | Why |
|---|---|---|
| Platform | Shopify | Predictable signals (`cdn.shopify.com`, `/cart.js`), largest DTC market share |
| Market | **US first** | Larger budgets, faster payment cycles, simpler compliance than most markets. Expand to GB → CA → AU only once US converts |
| Niche | Beauty / skincare | High repeat-purchase LTV, heavy trust/CRO surface area, strong ad spend (see §3) |
| Qualifier | Actively running Meta ads | Budget + belief in growth, in one signal — see §4 |
| Wedge offer | Free/low-cost mobile revenue-leak audit | Zero-commitment entry point, builds proof fast |
| Budget | No paid APIs to start | Public signals + smart engineering; add paid tools only after revenue (see §9) |
| Automation style | Human-in-the-loop | Every outreach reviewed and sent manually. No mass spam. |

## 3. Why beauty/skincare, why US-first

**Beauty/skincare:**
- High repeat-purchase potential (cleansers, serums, subscriptions) →
  higher LTV → brands can afford to spend on ads, CRO, design, SEO.
- Heavy trust requirement (ingredients, reviews, before/after, safety) →
  lots of legitimate CRO/design findings, not manufactured ones.
- Strong mobile-first buying behavior → the mobile audit checklist (§5)
  has real teeth in this niche.
- Strong PPC fit: brands running Meta/TikTok/Google Shopping ads into a
  weak product page is *the* pitch — "your traffic isn't the problem,
  your conversion path is leaking."

**US first, specifically:**
- Larger ad budgets and DTC spend than most other English-speaking markets.
- Faster decision cycles for the $500k–$10M revenue range we're targeting
  (§6) — founders/growth leads can say yes without procurement.
- Simpler cold-outreach compliance (CAN-SPAM) to get right before adding
  GDPR complexity for UK/EU expansion.

**Fallback niches** (if beauty/US doesn't convert after ~20 real
outreach attempts — see §8 for what "doesn't convert" means):
recurring-purchase, ad-heavy, high-trust categories work the same way —
supplements/vitamins, pet food & treats, coffee/tea subscriptions,
specialty food & snacks. Swap `NICHE_PRESETS` in `config.py`; the
pipeline code doesn't change.

## 4. Target client profile

- Shopify beauty/skincare brand
- Actively running Meta (and later TikTok) ads — this is now a *filter*,
  not a guess, via the Ad Library API (see §5, Discovery)
- Estimated $500k–$10M annual revenue (inferred from product count,
  review count, ad activity — we can't know exact revenue without paid
  data, and we don't need to)
- Too small = no budget. Too large = slow procurement. Mid-range = a
  founder or growth lead can say yes quickly.
- Decision-maker: usually the founder for smaller brands; CMO/e-commerce
  manager/growth marketer for the upper end of the range.

## 5. The pipeline (what the code actually does)

```
Meta Ad Library search (niche keywords, US)
        ↓
resolve landing domain from ad snapshot (og:url → CTA link → any link)
        ↓
confirm Shopify (cdn.shopify.com / cart.js / theme signals)
        ↓
mobile CRO audit (Playwright): load speed, popups, Add to Cart
visibility, express checkout, review widgets — each with a screenshot
        ↓
opportunity score (transparent, severity-weighted, 0–10)
        ↓
client-ready HTML report, ranked leads CSV
        ↓
draft outreach email referencing the single most severe real issue
        ↓
[YOU review everything here — nothing sends automatically]
        ↓
you personalize and send from your real inbox
```

Module map (see `src/revenue_leak_engine/`):
- `discovery/meta_ads_search.py` — Ad Library search + landing-domain resolution
- `qualification/shopify_detect.py` — Shopify confidence scoring
- `audit/site_audit.py` — the mobile CRO checklist
- `reporting/report_generator.py` — HTML reports + opportunity scoring
- `outreach/outreach_draft.py` — draft generation, CSV logging
- `pipeline.py` — orchestrates all of the above

## 6. Service ladder (what you're actually selling)

| Level | Deliverable | Price |
|---|---|---|
| 1. Free teardown | 3-5 leaks, short report, Loom | Free — build proof |
| 2. Paid Revenue Leak Audit | Full client-ready audit | $497 – $1,500 |
| 3. Conversion Fix Sprint | Implement top fixes | $2,000 – $7,500 |
| 4. Landing Page / Funnel Build | Ad-specific landing pages, quizzes, bundles | $2,500 – $10,000 |
| 5. Paid Traffic / PPC | Campaign setup, pixel cleanup, retargeting | $1,500 – $5,000/mo |
| 6. SEO | Ingredient pages, schema, technical SEO | $1,500 – $5,000/mo |
| 7. Ongoing CRO | Monthly testing, heatmaps, funnel iteration | $2,000 – $7,500/mo |

The audit (Level 2) is the wedge. Everything above it is upsold *after*
trust is established with real evidence, not pitched cold.

## 7. What "worth it" actually depends on

This is a service business, not a product with near-zero marginal cost
per user. Revenue scales with your hours (audits, sprints, calls,
delivery), not with code shipped. That means:
- The code's job is to remove *your* bottleneck (finding qualified
  leads, writing first-draft reports) — not to replace the sales and
  delivery work, which is still you.
- Time budget matters more here than in a SaaS. Track hours per closed
  client from the start (§10) so you know your real hourly rate on this,
  not just gross revenue.
- If close rate or deal size doesn't support your target hourly rate
  after ~20 real outreach attempts, that's the signal to pivot niche
  (§3) or pricing (§6) — not to build more automation.

## 8. Milestones — build order

Each milestone has a concrete Definition of Done. Don't start the next
one until the current one is done — that's the whole point of this
sequencing.

### Milestone 1 — Pipeline runs end to end (infrastructure)
**Status: code complete, needs your Meta token to run live.**
- [x] Package structure, tests passing (`pytest tests/`)
- [x] Ad Library search + landing-domain resolution
- [x] Shopify detection
- [x] Mobile CRO audit with evidence screenshots
- [x] Report generation + opportunity scoring
- [x] Draft outreach generation (never auto-sends)

**Definition of done:** `rle-pipeline --niche beauty --limit 30` runs
without crashing and produces at least one real report from a live
Shopify beauty brand.

### Milestone 2 — First real batch
- [ ] Get a Meta developer token, fill in `.env`
- [ ] Run the pipeline against ~30 candidates
- [ ] **Manually spot-check** the first 10 resolved landing domains
  against their ad snapshot URLs — confirm `extract_landing_domain()`
  is grabbing the right link, not a secondary CTA
- [ ] Manually review every generated report before it counts as usable

**Definition of done:** 10+ audited, human-verified reports for real US
Shopify beauty brands running ads.

### Milestone 3 — First outreach
- [ ] Pick the top 10-20 by opportunity score from the ranked CSV
- [ ] Personalize each draft — the auto-draft is a starting point, not a
  final email
- [ ] Send from your real inbox, with a working opt-out
- [ ] Log replies manually (see `data/logs/`)

**Definition of done:** 20 personalized emails sent, reply rate known.

### Milestone 4 — Learn and decide
- [ ] If you got replies/calls: double down — automate whatever step ate
  the most manual time in Milestones 2-3 (likely contact-finding next)
- [ ] If you got near-zero replies after 20 genuinely good, personalized
  emails: that's real signal. Revisit niche (§3 fallback list) or offer
  (§6) before touching more code

**Definition of done:** a data-backed decision, not a guess, about
whether to scale this niche or pivot.

### Milestone 5+ — Scale what worked (only after Milestone 4)
- TikTok Ad Library integration (same pattern as Meta)
- Contact/email enrichment automation
- Expand market to GB (see §3 sequencing)
- CRM / pipeline tracking once there's more than a spreadsheet's worth
  of active conversations

Don't build these earlier. They're listed so you have a plan, not so
you start on them now.

## 9. No-budget data strategy

No paid APIs to start. What we use instead:
- **Meta Ad Library API** — free, public, no special approval needed for
  commercial (non-political) ads. This is the core budget/intent signal.
- **Public site signals** — `cdn.shopify.com`, `/cart.js`, review-app
  script tags, express-checkout markers — all visible in page HTML.
- **Playwright** — free, self-hosted mobile audit instead of a paid
  Lighthouse/PageSpeed API tier.

**Add later, only after revenue** (Milestone 5+): TikTok Ads API,
BuiltWith, Hunter/Apollo for contact enrichment, a proper CRM. Buying
these before you've closed a client is optimizing a bottleneck you
haven't confirmed you have.

## 10. Metrics to track from day one

**Pipeline metrics** (the code can log these):
- candidates found → Shopify-confirmed → successfully audited → reports generated

**Business metrics** (you track these manually, e.g. a simple sheet):
- outreach sent, reply rate, call-booked rate, close rate
- **hours spent per closed client** — this is the one that tells you if
  the niche/offer actually supports your target income, not just
  whether it "works" in principle

## 11. Risk management

| Risk | Mitigation |
|---|---|
| Sites block automation | Respect blocks, mark `manual_review`, never bypass CAPTCHAs |
| False positives in audit findings | Confidence scores, screenshots, human review before any claim goes in an email |
| Wrong landing domain resolved from ad snapshot | Spot-check first batch (Milestone 2); og:url/CTA priority + redirect unwrapping already reduces this |
| Outreach flagged as spam | Personalized, low-volume, human-approved, real sender identity, working opt-out, suppression list respected |
| Beauty claims become legally risky | Avoid medical/cure/treatment language; stick to UX, conversion, tracking, design |
| Overbuilding before first client | This roadmap's entire structure — don't skip ahead to Milestone 5 |

## 12. Compliance — you're already doing the right things

You said you're using your real credentials and are aware of spam/
deception concerns. Concretely, that means:
- Real sending identity, real reply-to address, working unsubscribe.
- Respect `data/suppression_list.csv` — never re-contact anyone who
  opts out, ever.
- Never bypass CAPTCHAs or paywalls — mark as `manual_review` and move on.
- Keep volume low and personalized. If it ever starts to feel like it
  could be mistaken for a spam operation, it's grown too fast — slow down.

## 13. Immediate next steps

1. `pip install -e ".[dev]"` and `playwright install chromium`
2. Get a Meta developer token, fill in `.env`
3. Run `pytest tests/` — confirm the 12 existing tests still pass in your
   environment
4. Run `rle-pipeline --niche beauty --limit 30 --country US`
5. Manually verify the first 10 results (Milestone 2) before trusting the
   pipeline's output at face value
