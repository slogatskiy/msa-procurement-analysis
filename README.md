# MSA Safety — U.S. Public Procurement Analysis

Research project analyzing **MSA Safety Incorporated** (NYSE: MSA, formerly Mine Safety
Appliances Co.) participation and wins in U.S. public procurement (federal contract
tenders) over 2021–2026. Built as supporting evidence for an investment thesis.

🔗 **Live site:** https://slogatskiy.github.io/msa-procurement-analysis/

**Headline:** 542 federal prime contract awards · **$143.5M** (2021–2026) · Fire/SCBA 73%,
Detection 23% · 10 agencies · 26 states.

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
- **USAspending.gov API** — federal prime & sub-award contract data (primary).
- **SAM.gov** — federal opportunities/solicitations (context, optional).
- **FEMA Assistance to Firefighters Grants (AFG)** — SCBA demand proxy (context).

## Refresh / backup
All data is reproducible from the API — no manual entry. To refresh:

```bash
python3 scripts/collect_federal.py    # re-pulls awards into data/
```

Then rebuild/commit the site. Because everything regenerates from scripts, a full backup
is just this git repo.

> Note: `MSA_Thesis.docx` (the private thesis) is intentionally git-ignored and never
> published to this public repo.
