# MSA Safety — Public Procurement / Tender Analysis · ROADMAP

**Goal:** Build a shareable, public GitHub Pages research site documenting MSA Safety's
participation and wins in U.S. public procurement (tenders) over the last ~5 years
(2021–2026), as supporting evidence for the investment thesis (`MSA_Thesis.docx`).

**Company:** MSA Safety Incorporated (formerly Mine Safety Appliances Company).
Federal recipient entities seen in data:
- `MSA SAFETY SALES, LLC`
- `MSA SAFETY INCORPORATED`
- `MINE SAFETY APPLIANCES COMPANY` / `MINE SAFETY APPLIANCES COMPANY, LLC`

**Scope:** United States. Primary = federal contract awards. Secondary/context =
federal opportunities (bids), AFG firefighter grants (demand proxy), best-effort
state/local. Window: 2021-01-01 → present.

**Deliverable:** One-page static site on GitHub Pages, shareable by link, styled like
the reference design (research-report layout: anchor nav, KPI tiles, charts with
"What this means / What to watch" panels, tables, source attribution per block).

---

## Phases & Checklist

### Phase 0 — Project setup & infrastructure
- [ ] Repo scaffold (`/data`, `/scripts`, `/site`, `/docs`), `.gitignore`, `README.md`
- [ ] `git init` + first commit
- [ ] Create **public** GitHub repo and push
- [ ] Enable GitHub Pages (serve from `/site` or `/docs`)

### Phase 1 — Federal data collection (USAspending.gov API)
- [ ] Resolve all MSA recipient entities (UEI / DUNS)
- [ ] Pull ALL prime contract awards 2021–2026 (paginated, full)
- [ ] Pull sub-awards where MSA is sub-recipient
- [ ] Save raw JSON + normalized CSV in `/data`
- [ ] Sanity checks (totals, dedupe, date coverage)

### Phase 2 — Enrichment & analysis
- [ ] Map awards to MSA segments via NAICS / PSC product codes
      (Fire/SCBA · Detection · Industrial PP&E)
- [ ] Aggregations: by year, by agency, by segment, by geography
- [ ] Identify top contracts + notable wins vs. thesis (fire replacement cycle, detection)
- [ ] (Optional) SAM.gov opportunities = tenders bid on, not just won
- [ ] (Context) FEMA AFG firefighter grants as SCBA demand proxy
- [ ] Write analysis notes (`/docs/findings.md`)

### Phase 3 — Site build (GitHub Pages)
- [ ] Page scaffold + anchor nav + design system (CSS) matching reference
- [ ] Section: Overview / thesis link / methodology
- [ ] Section: Federal contracts KPIs (total $, # awards, # agencies, CAGR)
- [ ] Section: Trend by year (chart)
- [ ] Section: By segment (chart)
- [ ] Section: By agency (chart + table)
- [ ] Section: Top contracts (table)
- [ ] Section: Geography
- [ ] Section: Context (AFG grants / opportunities)
- [ ] Section: Sources & methodology (full traceability)

### Phase 4 — Publish & handoff
- [ ] Push, verify Pages renders, capture public URL
- [ ] README with backup/refresh instructions (how to re-run collectors)
- [ ] Final review pass

---

## v3 — PIVOT: municipal fire procurement (in progress, 2026-06-30)
PM feedback: nearly ALL of MSA's fire-segment revenue comes from MUNICIPALITIES (cities/
counties), not the federal government. Focus the whole project on the **fire segment only**
(drop Detection). Use an LLM to identify the websites that run municipal bidding systems, then
mine them for MSA participation. Scope decisions (from Stepan): deliver BOTH a platform map and a
pilot harvest; count participation as **MSA + known dealers**; geography **as broad as possible**.

- [ ] v3-1 Map municipal e-procurement platforms (PlanetBids, BidNet, Bonfire, OpenGov,
      DemandStar, Public Purchase, Ionwave...) + cooperative orgs (Sourcewell/OMNIA/NASPO).
- [ ] v3-2 MSA fire dealer list (MES, Fire Safety USA, Witmer, Casco...) + product terms
      (G1, Globe, Cairns) + competitor terms to exclude.
- [ ] v3-3 Minability / access methods per platform (public results? API? login/paid? ToS).
- [ ] v3-4 Pilot-harvest real municipal SCBA/turnout bids where MSA + dealers appear.
- [x] v3-5 Rebuilt site fire-only (Detection removed); federal demoted to supporting slice;
      new sections: municipal channel dominance, co-op contracts, platform landscape. Redeployed.

### v3 — SHIPPED (2026-06-30)
- Municipal sweep: MSA channel leads in **34 of 42** jurisdictions, present in **41 of 44**
  (raw count 17,022 vs 2,077 competitor — concentrated in top-3, so we lead with breadth).
- Co-op channel: MSA direct on Sourcewell/HGAC/GSA + indirect via Safeware (OMNIA/NASPO).
- Platform landscape + access reality (PlanetBids WAF, Bonfire robots-block, BidNet bans our bots).
- Tier-2 finding: free automated bid-tab scraping is walled off; "who-lost" needs FOIA/paid.
- Federal kept fire-only ($104M, SCBA cycle still visible).

Reframing note: the federal dataset ($143M) stays but becomes a small supporting section —
the municipal story is the main event.

## Conventions
- Raw API pulls saved verbatim under `data/raw/` (never edited by hand).
- Derived/normalized data under `data/processed/`.
- Every site chart/table cites its source + date refreshed.
- Collectors are re-runnable Python scripts (no manual data entry) for easy refresh/backup.

## Status log
- 2026-06-29: Project kickoff. Validated USAspending API returns rich MSA federal
  contract data (DoD/Air Force $28.5M, DHS/Coast Guard $15.3M, HHS, etc.). Roadmap created.
- 2026-06-29: **v1 SHIPPED.** Phases 0–4 complete. Collected 542 prime awards ($143.5M);
  classified into segments (Fire/SCBA 73%, Detection 23%); built + deployed the GitHub Pages
  site. Live: https://slogatskiy.github.io/msa-procurement-analysis/
- 2026-06-29: **v2 + v2.1 SHIPPED.** Added competition/GAO, state&local (Socrata), FEMA AFG,
  and trend-over-time charts. All committed, pushed, deployed (Pages green). Session paused.
  **Next session:** decide on Slack share (draft saved in gitignored `drafts/`); pick from v3 backlog.

## v2.1 — SHIPPED (2026-06-29) — trend-over-time charts
- [x] Segment mix by year (stacked): Fire/SCBA $55M (2024) → $6M (2025) pause, visible in raw data.
- [x] Awarding-agency mix by year (stacked): DoD/Air Force drove the 2023–24 surge.
- [x] State & local payments by year: LA 2012–14 ~$4M SCBA fleet buy → replacement window 2024–28.

## v2 — SHIPPED (2026-06-29)
- [x] Federal "competed vs sole-source" + bids-received (FPDS competition fields):
      $86.5M won in open competition vs $57M sole-source; 73 single-bid (brand-locked).
- [x] GAO bid-protest record: 2021 MSA win upheld vs 3M Scott (Air Force SCBA);
      1992 MSA loss to Draeger (Navy) — concrete "competed and sometimes lost" evidence.
- [x] State & local sweep (Socrata checkbooks): $4.8M direct MSA payments across 19
      jurisdictions (LA $4.0M, Kansas City, NJ, Delaware, NY State, Chicago, ...).
- [x] FEMA AFG demand proxy: ~$1.8B FY21–25 national grant volume, explained on-site.
- [x] Three new site sections + redeploy.

## Backlog / v3 ideas (not yet done)
- SAM.gov opportunities = solicitations MSA could bid on (needs API key).
- State/local BID TABULATIONS = the clean "MSA bid and lost" data (per-portal scraping).
- Federal sub-awards where MSA sells through a distributor (understated today).
- Competitor overlay (3M/Scott, Honeywell, Teledyne, Draeger) on the same agencies.
- Pretty labels for remaining small local Socrata domains.
