# MSA Safety — Municipal Fire-Procurement Landscape

_Research synthesis, 2026-06-30. Scope: U.S. municipal (city/county/fire-district) procurement of
MSA fire-segment products (SCBA, turnout gear, fire helmets). Detection is out of scope._

**Why this matters:** nearly all of MSA's fire-segment revenue comes from municipalities, not the
federal government. The federal dataset already built ($143M of prime contracts) is therefore a
small supporting slice. This document maps where municipal fire tenders live, how to mine them, and
how to recognize MSA participation (MSA + its dealers) vs. competitors.

---

## 1. The platform landscape (consolidated into ~4 networks)

The municipal e-procurement market has rolled up. Mining ~4 networks covers most formal volume.

| Platform | Network / owner | Open bids public? | Award results / bid tabs public? | Mine-ability |
|----------|-----------------|-------------------|----------------------------------|--------------|
| **PlanetBids** | Independent (CA-heavy) | Yes (no login) | Yes, agency-discretionary ("Bid Results" tab) | Behind **AWS WAF CAPTCHA** → needs headless browser |
| **BidNet Direct** | SOVRA (KKR; +Periscope, Vendor Registry) | Partial | Partial | **robots.txt bans Claude/Anthropic bots — DO NOT scrape** |
| **Bonfire** | Euna (+Ion Wave, DemandStar) | Partial | **Yes — "AWARDED" badge + winning vendor** | `{agency}.bonfirehub.com` JS/XHR → headless |
| **DemandStar / Euna OpenBid** | Euna | Yes (OpenBids browse) | Partial | robots **wide open**; SPA JSON → headless |
| **OpenGov Procurement** (ex-ProcureNow) | OpenGov | Yes (public portal pages) | Yes — preliminary bid tab within 24h + award notices | Predictable per-agency URLs |
| **Public Purchase** | Independent | Partial | Mostly login-gated | Weak; refuses non-browser clients |
| **Bid Express** | Infotech | Partial | **Yes (strong)** — automated bid tabs | DOT/heavy-civil skew → low SCBA hit-rate |
| **Municibid** | Independent | Yes | N/A — this is surplus **disposal** (used gear resale) | Replacement-cycle indicator only, not buy-side |

## 2. Cooperative purchasing — MSA's direct contracts (a thesis-relevant channel)

A large share of municipal SCBA/turnout buys **bypass competitive bidding** via cooperative
("piggyback") contracts. This is why competitive-bid data understates true MSA demand.

| Cooperative | MSA awarded contract? | Contract / detail |
|-------------|-----------------------|-------------------|
| **Sourcewell** | **Yes — direct** | `011824-MSS` — SCBA, RIT, Connected Firefighter, FireGrid, LUNAR |
| **HGACBuy** | **Yes — direct** | `EE11-24` — SCBA, turnout gear, boots, helmets, respirators |
| **GSA** (federal schedule) | **Yes — direct** | `47QSMS24D0018` — respirators, helmets, comms |
| **OMNIA Partners** | Indirect (via distributor Safeware) | Safeware OMNIA contract carries MSA SCBA + turnout |
| **NASPO ValuePoint** | Indirect (via Safeware) | "Rescue & Public Protection Equipment", award to Safeware, eff. Dec 2025 |
| **NPPGov / FireRescue GPO** | No direct MSA award | SCBA contracts held by dealers (MES, Ten-8), multi-brand |

Source: MSA co-op page `us.msasafety.com/co-op-contracts`.

## 3. MSA fire channel — dealers & product terms (for bid matching)

MSA publishes **no enumerated dealer list**; distributors are **territory-exclusive**. Count
participation as **MSA + known dealers**.

**Confirmed authorized MSA fire dealers:**
| Dealer | Territory | Notes |
|--------|-----------|-------|
| **Witmer Public Safety Group / TheFireStore** | Mid-Atlantic (DE, NJ, PA, MD, VA, DC) | MSA's #1 distributor |
| **Casco Industries** | TX, LA, OK, AR (SW/S-central) | ~65% of line = Globe + MSA |
| **MacQueen Emergency** | Upper Midwest (MN, WI, IA, NE, SD, IL, IN, MI) | G1 SCBA, factory service |
| **Vogelpohl Fire Equipment** | KY + parts OH/IN | MSA SCBA service/warranty center |
| **Sentinel Emergency Solutions** | MO, IL, IN | MSA SCBA sales + service |
| _Probable_: Sunbelt Fire (AL/SE), FDSAS, Firematic (NE), Ten-8 (FL/SE) | — | authorization not explicit |

**⚠️ Corrections to earlier assumptions:**
- **MES (Municipal Emergency Services)** — as of Feb 2026 became a **Dräger** AirBoss partner; MSA
  allegiance uncertain. Do **not** treat MES as MSA-by-default.
- **Fire Safety USA** — MSA authorization unverified.

**MSA fire product search terms:**
- SCBA: `MSA G1`, `G1 XR`, `M1`, `FireHawk M7`/`M7XT`, `FireHawk XT`, `AirHawk`
- Turnout (Globe, an MSA co.): `Globe`, `ATHLETIX`, `G-XCEL`, `GX-7`, `AXTION`, `SILIZONE`
- Helmets (Cairns, an MSA co.): `Cairns`, `1010`, `1044`, `N5A New Yorker`, `N6A Houston`, `XF1`, `660 Metro`
- Other: `LUNAR`, `Connected Firefighter`, `EVOLUTION` (TIC)

**Competitor terms (to exclude / tag as competitor wins):**
- SCBA: Scott `Air-Pak X3`/`75i`, `AV-3000`, `Scott Sight`; Dräger `PSS 7000`/`4000`/`AirBoss`; (Survivair = legacy)
- Turnout: LION `V-Force`/`RedZone`/`Janesville`; Honeywell `Morning Pride`/`Ranger`; `Fire-Dex AeroFlex`; `Veridian`

## 4. Recommended harvest plan (free, legal, structured first)

**Tier 1 — best free structured data (build here first):**
1. **Socrata SODA APIs** on city open-data portals — extend our existing `collect_socrata.py` to a
   fire-focused sweep: contract-award / PO / payment datasets filtered on SCBA/turnout keywords +
   MSA/dealer/competitor vendor names. Confirmed targets: NYC FDNY awards (`qyyg-4tf5`), Chicago
   (`rsxa-ify5`), LA (`5ru3-n8sy`), Baton Rouge, etc. Free, open license, lowest legal risk.
2. **Virginia eVA** open-data CSVs (`data.virginia.gov`) — state + **900+ local governments**;
   awards public; filter for SCBA/turnout/vendor. Best single municipal source.
3. **USAspending** — already built; refilter to fire-only + FEMA AFG-funded buys (federal supplement).

**Tier 2 — bid-platform award detail (optional, heavier; headless browser):**
- **Bonfire** `pastOpportunities` (per-agency subdomains; AWARDED + vendor) and **DemandStar**
  (robots open) via Playwright — to capture winning-vendor detail open-data POs may lack.
- **PlanetBids** "Bid Results" via headless browser that passes the WAF challenge (CA fire agencies,
  e.g. Orange County Fire Authority) — richest who-bid/who-won/price, but most friction.

**Tier 3 — targeted gaps:** FOIA the specific fire dept / city purchasing office for individual bid
tabulations with competitor line-item pricing.

**Avoid:** BidNet (bans our bots), paid aggregators (GovSpend, GovWin, BidPrime — subscription).

### Legal posture
Prefer truly public open-data endpoints (no login). Rate-limit, respect robots.txt, never use fake
accounts or scrape behind registration. Government public-records data has the strongest footing —
which is exactly why Tier 1 is both easiest and safest.

## 5. Caveats
- Award/tabulation completeness on bid platforms is **agency-discretionary** → expect gaps.
- Cooperative-channel buys (Sourcewell/HGAC/OMNIA) may never appear as a competitive solicitation →
  triangulate, don't treat competitive-bid volume as total demand.
- Dealer-won bids attribute to the dealer, not MSA → match on product terms + dealer names.
