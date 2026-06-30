# MSA Safety — U.S. Public Procurement Analysis

Research project analyzing **MSA Safety Incorporated** (NYSE: MSA, formerly Mine Safety
Appliances Co.) participation and wins in U.S. public procurement (federal contract
tenders) over 2021–2026. Built as supporting evidence for an investment thesis.

🔗 **Live site:** https://slogatskiy.github.io/msa-procurement-analysis/

**Headline:** 542 federal prime contract awards · **$143.5M** (2021–2026) · Fire/SCBA 73%,
Detection 23% · 10 agencies · 26 states. Plus: **$86.5M won in open competition** vs rivals
· **$4.8M** direct state/local payments across **19 jurisdictions** · **~$1.8B** national FEMA
AFG demand pool · GAO bid-protest record vs 3M Scott & Draeger.

## What's here

| Path | Contents |
|------|----------|
| `ROADMAP.md` | Project plan & progress checklist |
| `scripts/` | Re-runnable Python data collectors (USAspending.gov API) |
| `data/raw/` | Verbatim API pulls (never hand-edited) |
| `data/processed/` | Normalized CSV/JSON used by the site |
| `site/` | Static GitHub Pages site (the shareable deliverable) |
| `docs/` | Analysis notes & findings |

## Data sources
- **USAspending.gov API** — federal prime contract awards + competition fields (primary).
- **Socrata government open-data checkbooks** — automated sweep of state/county/city
  vendor-payment portals for payments booked to MSA (state & local footprint).
- **FEMA Assistance to Firefighters Grants (AFG)**, Assistance Listing 97.044 — SCBA demand proxy.
- **GAO bid-protest decisions** — hand-verified head-to-head cases vs competitors.

## Collectors (v3 — fire segment focus)
```bash
python3 scripts/collect_federal.py    # federal prime awards + competition (filtered to fire in build)
python3 scripts/collect_municipal.py  # municipal fire sweep (Socrata award/PO datasets, MSA+dealers vs competitors)
python3 scripts/collect_afg.py        # FEMA AFG grant volume by year (fire demand proxy)
python3 scripts/build_site.py         # -> fire-only site_data.json + site/data.js
```
See `docs/municipal-landscape.md` for the bidding-platform map, MSA dealer/co-op channel, and data-access reality.

## Refresh / backup
All data is reproducible from the API — no manual entry. To refresh:

```bash
python3 scripts/collect_federal.py    # re-pulls awards into data/
```

Then rebuild/commit the site. Because everything regenerates from scripts, a full backup
is just this git repo.

> Note: `MSA_Thesis.docx` (the private thesis) is intentionally git-ignored and never
> published to this public repo.
