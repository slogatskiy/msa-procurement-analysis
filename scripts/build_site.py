#!/usr/bin/env python3
"""
Build the FIRE-ONLY site_data for the MSA municipal-fire tracker (v3).

Combines:
  - Federal FIRE contracts (awards.csv, segment == Fire), demoted to a supporting slice
  - Municipal channel dominance (municipal_hits.json) — robust transaction COUNTS
  - MSA cooperative-purchasing contracts (static research)
  - Municipal bidding-platform landscape + access reality (static research)
  - FEMA AFG demand (afg.json)

Detection and other non-fire segments are EXCLUDED per PM direction.

Writes: data/processed/site_data.json  and  site/data.js
"""
import os
import csv
import json
import collections

import build_analysis as ba  # reuse classify(), competition(), agg(), amt(), FIRE
import collect_municipal as cm  # reuse clean_classify(), term lists, to_float()

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC = os.path.join(ROOT, "data", "processed")
RAW = os.path.join(ROOT, "data", "raw")
GENERATED = "2026-06-30"

TRUSTED_AMOUNT_DOMAINS = {
    "controllerdata.lacity.org", "data.cityofnewyork.us", "data.cityofchicago.org",
    "data.cincinnati-oh.gov", "data.kcmo.org",
}
LABEL = {
    "data.cityofnewyork.us": ("New York City, NY", "city"), "data.cityofchicago.org": ("Chicago, IL", "city"),
    "controllerdata.lacity.org": ("Los Angeles, CA", "city"), "data.cincinnati-oh.gov": ("Cincinnati, OH", "city"),
    "data.kcmo.org": ("Kansas City, MO", "city"), "data.richmondgov.com": ("Richmond, VA", "city"),
    "www.transparentrichmond.org": ("Richmond, VA", "city"), "atlanta.data.socrata.com": ("Atlanta, GA", "city"),
    "data.princegeorgescountymd.gov": ("Prince George's County, MD", "county"),
    "www.dallasopendata.com": ("Dallas, TX", "city"), "illinois-edp.data.socrata.com": ("Urbana, IL", "city"),
    "data.providenceri.gov": ("Providence, RI", "city"), "albany.data.socrata.com": ("Albany, NY", "city"),
    "data.colorado.gov": ("Colorado", "state"), "data.mo.gov": ("Missouri", "state"),
    "data.framinghamma.gov": ("Framingham, MA", "city"), "opendata.cityofmesquite.com": ("Mesquite, TX", "city"),
    "performance.ci.janesville.wi.us": ("Janesville, WI", "city"), "janesville.data.socrata.com": ("Janesville, WI", "city"),
    "data.vermont.gov": ("Vermont", "state"), "data.oregon.gov": ("Oregon", "state"),
    "data.montgomerycountymd.gov": ("Montgomery County, MD", "county"), "data.pa.gov": ("Pennsylvania", "state"),
    "johnstonia.data.socrata.com": ("Johnston, IA", "city"), "data.fultoncountyga.gov": ("Fulton County, GA", "county"),
    "sharefulton.fultoncountyga.gov": ("Fulton County, GA", "county"), "datacatalog.cookcountyil.gov": ("Cook County, IL", "county"),
    "corstat.coronaca.gov": ("Corona, CA", "city"), "citydata.mesaaz.gov": ("Mesa, AZ", "city"),
    "opendata.howardcountymd.gov": ("Howard County, MD", "county"), "stateofalaska.data.socrata.com": ("Alaska", "state"),
    "data.delaware.gov": ("Delaware", "state"), "data.coloradosprings.gov": ("Colorado Springs, CO", "city"),
    "data.macoupincountyil.gov": ("Macoupin County, IL", "county"), "newcastle.data.socrata.com": ("Newcastle, WA", "city"),
    "data.ny.gov": ("New York State", "state"), "data.nj.gov": ("New Jersey", "state"),
    "data.ct.gov": ("Connecticut", "state"),
}

DEALER_CANON = [
    ("WITMER", "Witmer / TheFireStore"), ("THEFIRESTORE", "Witmer / TheFireStore"),
    ("MUNICIPAL EMERGENCY", "Municipal Emergency Services (MES)"),
    ("CASCO", "Casco Industries"), ("MACQUEEN", "MacQueen Emergency"),
    ("VOGELPOHL", "Vogelpohl Fire"), ("SENTINEL EMERGENCY", "Sentinel Emergency"),
    ("SUNBELT FIRE", "Sunbelt Fire"), ("FIREMATIC", "Firematic"),
    ("TEN-8", "Ten-8 Fire & Safety"), ("FIRE SAFETY USA", "Fire Safety USA"),
]

COOP = [
    {"coop": "Sourcewell", "type": "Direct", "contract": "011824-MSS",
     "products": "SCBA, RIT, Connected Firefighter, FireGrid, LUNAR"},
    {"coop": "HGACBuy", "type": "Direct", "contract": "EE11-24",
     "products": "SCBA, turnout gear, boots, fire/rescue helmets, respirators"},
    {"coop": "GSA Schedule", "type": "Direct", "contract": "47QSMS24D0018",
     "products": "Respirators, fire/rescue helmets, communications"},
    {"coop": "OMNIA Partners", "type": "Indirect — via Safeware", "contract": "Safeware OMNIA",
     "products": "MSA SCBA + turnout gear"},
    {"coop": "NASPO ValuePoint", "type": "Indirect — via Safeware", "contract": "Rescue & Public Protection (eff. Dec 2025)",
     "products": "MSA products"},
]

PLATFORMS = [
    {"name": "PlanetBids", "network": "Independent (CA-heavy)", "awards": "Public (agency-discretionary)",
     "mine": "AWS WAF CAPTCHA — blocked to automated access"},
    {"name": "OpenGov Procurement", "network": "OpenGov", "awards": "Yes — bid tab within 24h",
     "mine": "Public per-agency URLs — most minable"},
    {"name": "BidNet Direct", "network": "SOVRA (KKR)", "awards": "Partial",
     "mine": "robots.txt bans Anthropic/Claude bots — excluded"},
    {"name": "Bonfire", "network": "Euna", "awards": "Yes — 'AWARDED' badge + vendor",
     "mine": "robots.txt Disallow / — blocked"},
    {"name": "DemandStar", "network": "Euna", "awards": "Partial",
     "mine": "robots open; SPA needs API reverse-engineering"},
]


def canon_dealer(vendor):
    v = (vendor or "").upper()
    for key, name in DEALER_CANON:
        if key in v:
            return name
    return None


def build_municipal():
    path = os.path.join(RAW, "municipal_hits.json")
    if not os.path.exists(path):
        return None
    hits = json.load(open(path))
    by_class = collections.Counter()
    juris_by_class = collections.defaultdict(set)
    dealer_cnt = collections.Counter()
    dealer_juris = collections.defaultdict(set)
    juris = collections.defaultdict(lambda: {"level": "local", "msa": 0, "comp": 0})
    direct_floor = 0.0
    total_rows = 0

    for h in hits:
        if any(s in h["domain"] for s in cm.NON_US_SUBSTR):
            continue
        cls = cm.clean_classify(h.get("vendor"), h.get("description"))
        if cls is None:
            continue
        label, level = LABEL.get(h["domain"], (h.get("jurisdiction") or h["domain"], h.get("level") or "local"))
        total_rows += 1
        by_class[cls] += 1
        juris_by_class[cls].add(label)
        j = juris[label]
        j["level"] = level
        is_msa = cls in ("MSA direct", "MSA product spec'd", "Via MSA fire dealer")
        if is_msa:
            j["msa"] += 1
            d = canon_dealer(h.get("vendor")) or ("MSA (direct / spec'd)" if cls != "Via MSA fire dealer" else None)
            if d:
                dealer_cnt[d] += 1
                dealer_juris[d].add(h["jurisdiction"])
        elif cls == "Competitor":
            j["comp"] += 1
        if cls in ("MSA direct", "MSA product spec'd") and h["domain"] in TRUSTED_AMOUNT_DOMAINS:
            a = cm.to_float(h.get("amount"))
            if 0 < a < cm.MAX_SANE_AMOUNT:
                direct_floor += a

    msa_txns = by_class["MSA direct"] + by_class["MSA product spec'd"] + by_class["Via MSA fire dealer"]
    comp_txns = by_class["Competitor"]
    msa_j = juris_by_class["MSA direct"] | juris_by_class["MSA product spec'd"] | juris_by_class["Via MSA fire dealer"]
    comp_j = juris_by_class["Competitor"]
    all_j = set(juris)

    top_dealers = [{"name": k, "count": v, "jurisdictions": len(dealer_juris[k])}
                   for k, v in dealer_cnt.most_common(12)]
    active = [{"jurisdiction": k, "level": v["level"], "msa": v["msa"], "comp": v["comp"]}
              for k, v in juris.items() if v["msa"] or v["comp"]]
    by_juris = sorted(active, key=lambda x: -(x["msa"] + x["comp"]))
    msa_wins = sum(1 for j in active if j["msa"] > j["comp"])
    both_present = sum(1 for j in active if j["msa"] and j["comp"])
    top3_share = round(100 * sum(j["msa"] for j in by_juris[:3]) / msa_txns) if msa_txns else 0

    return {
        "msa_txns": msa_txns,
        "competitor_txns": comp_txns,
        "ratio": round(msa_txns / comp_txns, 1) if comp_txns else None,
        "total_jurisdictions": len(all_j),
        "msa_jurisdictions": len(msa_j),
        "competitor_jurisdictions": len(comp_j),
        "msa_wins_jurisdictions": msa_wins,
        "both_present_jurisdictions": both_present,
        "active_jurisdictions": len(active),
        "top3_share_pct": top3_share,
        "by_class": [{"class": k, "count": v} for k, v in by_class.most_common()],
        "top_dealers": top_dealers,
        "by_jurisdiction": by_juris,
        "msa_direct_floor_usd": round(direct_floor, 2),
        "total_rows": total_rows,
        "source": "Municipal/state open-data (Socrata) award & PO datasets",
    }


def build_federal_fire():
    rows = [r for r in csv.DictReader(open(os.path.join(PROC, "awards.csv")))]
    for r in rows:
        r["segment"] = ba.classify(r)
    fire = [r for r in rows if r["segment"] == ba.FIRE]
    total = sum(ba.amt(r) for r in fire)

    years = sorted({(r["start_date"] or "")[:4] for r in fire if (r["start_date"] or "")[:4] >= "2021"})
    by_year = []
    for y in years:
        yr = [r for r in fire if (r["start_date"] or "")[:4] == y]
        by_year.append({"year": y, "amount": round(sum(ba.amt(r) for r in yr), 2), "count": len(yr)})

    top = sorted(fire, key=ba.amt, reverse=True)[:15]
    top_list = [{
        "award_id": r["award_id"], "amount": ba.amt(r),
        "agency": r["awarding_agency"], "sub_agency": r["awarding_sub_agency"],
        "start_date": r["start_date"], "state": r["pop_state"],
        "description": (r["description"] or "")[:150],
        "url": f"https://www.usaspending.gov/award/{r['generated_internal_id']}",
    } for r in top]

    return {
        "total_dollars": round(total, 2),
        "total_awards": len(fire),
        "by_year": by_year,
        "by_agency": [{"agency": x["key"], "amount": x["amount"], "count": x["count"]}
                      for x in ba.agg(fire, lambda r: r["awarding_agency"])][:8],
        "by_state": [{"state": x["key"], "amount": x["amount"], "count": x["count"]}
                     for x in ba.agg(fire, lambda r: r["pop_state"]) if x["key"]][:12],
        "competition": ba.competition(fire),
        "top_contracts": top_list,
    }


def main():
    afg = None
    p = os.path.join(PROC, "afg.json")
    if os.path.exists(p):
        afg = json.load(open(p))

    data = {
        "meta": {
            "generated": GENERATED,
            "scope": "MSA fire segment only (SCBA, turnout gear, fire helmets). Detection excluded.",
            "window": {"start": "2021-01-01", "end": "2026-06-30"},
        },
        "municipal": build_municipal(),
        "coop": COOP,
        "platforms": PLATFORMS,
        "federal_fire": build_federal_fire(),
        "afg": afg,
    }

    with open(os.path.join(PROC, "site_data.json"), "w") as f:
        json.dump(data, f, indent=2)
    with open(os.path.join(ROOT, "site", "data.js"), "w") as f:
        f.write("window.SITE_DATA = ")
        json.dump(data, f, indent=2)
        f.write(";\n")

    m = data["municipal"]; ff = data["federal_fire"]
    print("=== FIRE-ONLY SITE DATA ===")
    print(f"Municipal: MSA-channel {m['msa_txns']} txns vs competitor {m['competitor_txns']} "
          f"(ratio {m['ratio']}:1) across {m['total_jurisdictions']} US jurisdictions")
    print(f"  MSA direct $ floor (trusted datasets): ${m['msa_direct_floor_usd']:,.0f}")
    print(f"  top dealers: {', '.join(d['name'] for d in m['top_dealers'][:5])}")
    print(f"Federal fire: ${ff['total_dollars']:,.0f} across {ff['total_awards']} awards")
    print(f"AFG: {'loaded' if afg else 'missing'}")
    print("Wrote site_data.json + site/data.js")


if __name__ == "__main__":
    main()
