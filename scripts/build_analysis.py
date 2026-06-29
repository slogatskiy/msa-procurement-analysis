#!/usr/bin/env python3
"""
Analyze normalized MSA federal awards and emit site_data.json for the GitHub Pages site.

Reads:  data/processed/awards.csv
Writes: data/processed/site_data.json   (all aggregates the site renders)
        docs/findings.md                 (human-readable summary)

Segment mapping rationale (priority: description keywords -> PSC -> NAICS):
  * Fire Services (SCBA)  - SCBA breathing apparatus, cylinders, fire helmets, Globe/Cairns
  * Detection             - gas detectors/monitors, hazard-detecting & test instruments (ALTAIR)
  * Industrial PPE        - hard hats / safety helmets (V-Gard), fall protection, apparel
"""
import csv
import json
import os
import collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC = os.path.join(ROOT, "data", "processed")
CSV = os.path.join(PROC, "awards.csv")
OUT = os.path.join(PROC, "site_data.json")
FINDINGS = os.path.join(ROOT, "docs", "findings.md")
GENERATED = "2026-06-29"  # date refreshed (script env forbids Date.now equivalents)

FIRE = "Fire Services (SCBA)"
DETECT = "Detection"
INDUS = "Industrial PPE"
OTHER = "Other / Unclassified"

DETECT_KW = ["GAS DETECT", "DETECTOR", "GAS MONITOR", "MULTIGAS", "MULTI-GAS", "MULTI GAS",
             "ALTAIR", "PHOTOIONIZATION", "CALIBRATION GAS", "CAL GAS", "GAS MONITORING"]
FIRE_KW = ["SCBA", "SELF-CONTAINED BREATHING", "SELF CONTAINED BREATHING", "BREATHING APPARATUS",
           "AIR MASK", "AIR PACK", "AIRPACK", " G1", "G-1", "CAIRNS", "GLOBE", "TURNOUT",
           "FIRE HELMET", "FIREFIGHT", "FIRE FIGHT", "AIR CYLINDER", "CYLINDER", "FACEPIECE",
           "FACE PIECE", "REGULATOR ASSEMBLY"]
INDUS_KW = ["SAFETY HELMET", "HARD HAT", "HARDHAT", "V-GARD", "VGARD", "CONSTRUCTION WORKER",
            "FALL PROTECT", "HARNESS", "LANYARD", "FACE SHIELD", "FACESHIELD", "GOGGLE",
            "HEAD PROTECTION", "VISOR", "OUTERWEAR"]

DETECT_PSC = {"6665", "6625", "6630", "6635"}
FIRE_PSC = {"4240", "4210", "4220", "8120", "8125", "6830"}  # 8120/8125/6830 = cylinders/gases for SCBA
INDUS_PSC = {"8405", "8415", "8470", "8430", "5340"}

DETECT_NAICS = {"334511", "334512", "334513", "334514", "334516", "334412", "334419"}
FIRE_NAICS = {"339113"}
INDUS_NAICS = {"315999", "315990", "339993", "315220", "315280"}


def classify(r):
    text = (r["description"] or "").upper()
    psc = (r["psc_code"] or "").strip()
    naics = (r["naics_code"] or "").strip()
    if any(k in text for k in DETECT_KW):
        return DETECT
    if any(k in text for k in FIRE_KW):
        return FIRE
    if any(k in text for k in INDUS_KW):
        return INDUS
    if psc in DETECT_PSC:
        return DETECT
    if psc in FIRE_PSC:
        return FIRE
    if psc in INDUS_PSC:
        return INDUS
    if naics in DETECT_NAICS:
        return DETECT
    if naics in FIRE_NAICS:
        return FIRE
    if naics in INDUS_NAICS:
        return INDUS
    return OTHER


def amt(r):
    try:
        return float(r["award_amount"] or 0)
    except ValueError:
        return 0.0


def agg(rows, key):
    d_amt = collections.defaultdict(float)
    d_cnt = collections.Counter()
    for r in rows:
        k = key(r)
        d_amt[k] += amt(r)
        d_cnt[k] += 1
    out = [{"key": k, "amount": round(v, 2), "count": d_cnt[k]} for k, v in d_amt.items()]
    out.sort(key=lambda x: x["amount"], reverse=True)
    return out


EXTENT_LABEL = {
    "A": "Full & open competition", "B": "Not available for competition",
    "C": "Not competed (sole source)", "D": "Full & open after exclusion",
    "E": "Follow-on to competed action", "F": "Competed under SAP",
    "G": "Not competed under SAP",
}
COMPETED_CODES = {"A", "D", "F"}


def competition(rows):
    buckets = collections.Counter()
    comp_amt = {"competed": 0.0, "not_competed": 0.0}
    comp_cnt = {"competed": 0, "not_competed": 0}
    offers = {"1 (sole bid)": 0, "2": 0, "3-4": 0, "5+": 0}
    have_extent = 0
    for r in rows:
        ext = (r.get("extent_competed") or "").strip()
        if ext:
            have_extent += 1
            buckets[ext] += 1
            key = "competed" if ext in COMPETED_CODES else "not_competed"
            comp_amt[key] += amt(r)
            comp_cnt[key] += 1
        n = (r.get("number_of_offers") or "").strip()
        if n.isdigit():
            ni = int(n)
            if ni <= 1:
                offers["1 (sole bid)"] += 1
            elif ni == 2:
                offers["2"] += 1
            elif ni <= 4:
                offers["3-4"] += 1
            else:
                offers["5+"] += 1
    return {
        "have_extent": have_extent,
        "extent": [{"code": k, "label": EXTENT_LABEL.get(k, k), "count": v}
                   for k, v in sorted(buckets.items(), key=lambda x: -x[1])],
        "competed_vs_not": {
            "competed": {"amount": round(comp_amt["competed"], 2), "count": comp_cnt["competed"]},
            "not_competed": {"amount": round(comp_amt["not_competed"], 2), "count": comp_cnt["not_competed"]},
        },
        "offers": [{"bucket": k, "count": v} for k, v in offers.items()],
        "offers_total": sum(offers.values()),
    }


def stacked_by_year(rows, key_fn, top_keys, min_year=2021):
    """Return {years:[...], series:[{key, values:[...]}]} for a stacked time series."""
    years = sorted({(r["start_date"] or "")[:4] for r in rows
                    if (r["start_date"] or "")[:4] >= str(min_year)})
    mat = {k: {y: 0.0 for y in years} for k in top_keys}
    other = {y: 0.0 for y in years}
    for r in rows:
        y = (r["start_date"] or "")[:4]
        if y not in years:
            continue
        k = key_fn(r)
        if k in mat:
            mat[k][y] += amt(r)
        else:
            other[y] += amt(r)
    series = [{"key": k, "values": [round(mat[k][y], 2) for y in years]} for k in top_keys]
    if any(v > 0 for v in other.values()):
        series.append({"key": "Other", "values": [round(other[y], 2) for y in years]})
    return {"years": years, "series": series}


def load_optional(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return None


def main():
    rows = list(csv.DictReader(open(CSV)))
    for r in rows:
        r["segment"] = classify(r)

    total = sum(amt(r) for r in rows)
    years = sorted({(r["start_date"] or "")[:4] for r in rows if r["start_date"]})

    by_year_map = {y: {"amount": 0.0, "count": 0} for y in years}
    for r in rows:
        y = (r["start_date"] or "")[:4]
        if y in by_year_map:
            by_year_map[y]["amount"] += amt(r)
            by_year_map[y]["count"] += 1
    by_year = [{"year": y, "amount": round(v["amount"], 2), "count": v["count"]}
               for y, v in sorted(by_year_map.items())]

    top_contracts = sorted(rows, key=amt, reverse=True)[:25]
    top_list = [{
        "award_id": r["award_id"],
        "recipient": r["recipient_name"],
        "amount": amt(r),
        "agency": r["awarding_agency"],
        "sub_agency": r["awarding_sub_agency"],
        "start_date": r["start_date"],
        "segment": r["segment"],
        "state": r["pop_state"],
        "description": (r["description"] or "")[:160],
        "url": f"https://www.usaspending.gov/award/{r['generated_internal_id']}",
    } for r in top_contracts]

    data = {
        "meta": {
            "generated": GENERATED,
            "window": {"start": "2021-01-01", "end": "2026-06-30"},
            "source": "USAspending.gov API (federal prime contract awards)",
            "total_awards": len(rows),
            "total_dollars": round(total, 2),
            "n_agencies": len({r["awarding_agency"] for r in rows if r["awarding_agency"]}),
            "n_sub_agencies": len({r["awarding_sub_agency"] for r in rows if r["awarding_sub_agency"]}),
            "n_states": len({r["pop_state"] for r in rows if r["pop_state"]}),
            "recipient_entities": sorted({r["recipient_name"] for r in rows}),
        },
        "by_year": by_year,
        "by_segment": [{"segment": x["key"], "amount": x["amount"], "count": x["count"]}
                       for x in agg(rows, lambda r: r["segment"])],
        "by_agency": [{"agency": x["key"], "amount": x["amount"], "count": x["count"]}
                      for x in agg(rows, lambda r: r["awarding_agency"])][:12],
        "by_sub_agency": [{"sub_agency": x["key"], "amount": x["amount"], "count": x["count"]}
                          for x in agg(rows, lambda r: r["awarding_sub_agency"])][:12],
        "by_state": [{"state": x["key"], "amount": x["amount"], "count": x["count"]}
                     for x in agg(rows, lambda r: r["pop_state"]) if x["key"]][:20],
        "by_recipient": [{"recipient": x["key"], "amount": x["amount"], "count": x["count"]}
                         for x in agg(rows, lambda r: r["recipient_name"])],
        "top_contracts": top_list,
        "by_segment_year": stacked_by_year(
            rows, lambda r: r["segment"],
            [FIRE, DETECT, INDUS]),
        "by_agency_year": stacked_by_year(
            rows, lambda r: r["awarding_agency"],
            [a["key"] for a in agg(rows, lambda r: r["awarding_agency"])[:4]]),
        "competition": competition(rows),
        "afg": load_optional(os.path.join(PROC, "afg.json")),
        "state_local": load_optional(os.path.join(PROC, "state_local.json")),
    }

    with open(OUT, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Wrote {OUT}")

    site_js = os.path.join(ROOT, "site", "data.js")
    os.makedirs(os.path.dirname(site_js), exist_ok=True)
    with open(site_js, "w") as f:
        f.write("window.SITE_DATA = ")
        json.dump(data, f, indent=2)
        f.write(";\n")
    print(f"Wrote {site_js}")

    write_findings(data)
    print_summary(data)


def write_findings(data):
    m = data["meta"]
    lines = [
        "# MSA Safety — Federal Procurement Findings",
        "",
        f"_Source: {m['source']}. Window {m['window']['start']} to {m['window']['end']}. "
        f"Refreshed {m['generated']}._",
        "",
        "## Headline",
        f"- **{m['total_awards']} federal prime contract awards** totaling "
        f"**${m['total_dollars']:,.0f}** over the period.",
        f"- Spread across **{m['n_agencies']} federal agencies** "
        f"({m['n_sub_agencies']} sub-agencies) and **{m['n_states']} states**.",
        f"- Recipient entities: {', '.join(m['recipient_entities'])}.",
        "",
        "## By segment",
    ]
    for s in data["by_segment"]:
        lines.append(f"- **{s['segment']}**: ${s['amount']:,.0f} ({s['count']} awards)")
    lines += ["", "## By year (award action start date)"]
    for y in data["by_year"]:
        lines.append(f"- {y['year']}: ${y['amount']:,.0f} ({y['count']} awards)")
    lines += ["", "## Top awarding agencies"]
    for a in data["by_agency"][:8]:
        lines.append(f"- {a['agency']}: ${a['amount']:,.0f} ({a['count']})")
    lines += ["", "## Largest contracts"]
    for c in data["top_contracts"][:10]:
        lines.append(f"- ${c['amount']:,.0f} — {c['agency']} / {c['sub_agency']} — "
                     f"{c['segment']} — {c['description']}")
    with open(FINDINGS, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Wrote {FINDINGS}")


def print_summary(data):
    print("\n=== SUMMARY ===")
    print(f"Total: {data['meta']['total_awards']} awards, ${data['meta']['total_dollars']:,.0f}")
    print("Segments:")
    for s in data["by_segment"]:
        print(f"  {s['segment']:24s} ${s['amount']:>14,.0f}  ({s['count']})")
    print("Years:")
    for y in data["by_year"]:
        print(f"  {y['year']}  ${y['amount']:>14,.0f}  ({y['count']})")


if __name__ == "__main__":
    main()
