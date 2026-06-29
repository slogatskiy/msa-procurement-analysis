#!/usr/bin/env python3
"""
Sweep Socrata-hosted government "checkbook" / vendor-payment datasets for payments to MSA.

Strategy (fully automated, no hand-curated dataset IDs):
  1. Use the Socrata discovery catalog to enumerate vendor-payment / checkbook /
     expenditure datasets across ALL Socrata domains (states, counties, big cities).
  2. For each dataset, auto-detect the vendor-name, amount and date columns.
  3. Server-side filter rows where vendor name matches MSA / Mine Safety Appliances.
  4. Aggregate hits by jurisdiction (domain).

Outputs:
  data/raw/socrata_hits.json          - every matched payment row (verbatim subset)
  data/processed/state_local.csv      - normalized matched rows
  data/processed/state_local.json     - aggregates by jurisdiction (for the site)

Caveats: captures payments booked DIRECTLY to MSA entities only (distributor/reseller
sales are invisible), and only jurisdictions that publish on Socrata. So true state/local
demand for MSA product is larger than shown.
"""
import json
import os
import time
import csv
import collections
import threading
import urllib.request
import urllib.parse
import urllib.error
import ssl
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import certifi
    SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:  # noqa: BLE001
    SSL_CTX = ssl.create_default_context()
    SSL_CTX.check_hostname = False
    SSL_CTX.verify_mode = ssl.CERT_NONE

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
PROC = os.path.join(ROOT, "data", "processed")

DISCOVERY = "https://api.us.socrata.com/api/catalog/v1"
SEARCH_TERMS = [
    "vendor payments", "checkbook", "vendor payment", "expenditures",
    "accounts payable", "supplier payments", "spending detail", "open checkbook",
    "purchase order", "payments to vendors",
]

# Vendor-name match terms for the server-side sweep (broad; cleaned afterwards).
MATCH = ["MINE SAFETY", "MSA SAFETY"]

# Post-sweep KEEP filter: only true MSA Safety entities. This drops look-alikes such as
# "MISSOURI MINE SAFETY & HEALTH", "MINE SAFETY ASSOCIATES", etc.
KEEP_VENDOR = ["MINE SAFETY APPLIANC", "MSA SAFETY"]
EXCLUDE_DOMAIN_SUBSTR = ["demo.socrata.com", "sandbox", ".test.", "test.socrata"]


def is_real_msa(vendor):
    v = (vendor or "").upper()
    return any(k in v for k in KEEP_VENDOR)


def excluded_domain(domain):
    return any(s in domain for s in EXCLUDE_DOMAIN_SUBSTR)

VENDOR_HINTS = ["vendor", "payee", "supplier", "merchant", "company", "recipient", "legal_name", "vendor_name"]
VENDOR_BAD = ["number", "id", "code", "type", "city", "state", "zip", "address", "dept", "department", "category"]
AMOUNT_HINTS = ["amount", "amt", "paid", "payment", "check", "total", "expended", "expense", "spend", "cost", "value"]
DATE_HINTS = ["date", "ending", "period", "fiscal", "year", "posted", "paid"]

# Pretty labels + gov level for notable domains (everything else falls back to the domain).
DOMAIN_LABEL = {
    "data.ny.gov": ("New York State", "state"),
    "data.vermont.gov": ("Vermont", "state"),
    "data.delaware.gov": ("Delaware", "state"),
    "data.ct.gov": ("Connecticut", "state"),
    "opendata.maryland.gov": ("Maryland", "state"),
    "data.texas.gov": ("Texas", "state"),
    "data.oregon.gov": ("Oregon", "state"),
    "data.wa.gov": ("Washington", "state"),
    "data.nj.gov": ("New Jersey", "state"),
    "data.mo.gov": ("Missouri", "state"),
    "data.colorado.gov": ("Colorado", "state"),
    "opendata.utah.gov": ("Utah", "state"),
    "data.pa.gov": ("Pennsylvania", "state"),
    "data.illinois.gov": ("Illinois", "state"),
    "datacatalog.cookcountyil.gov": ("Cook County, IL", "county"),
    "data.framinghamma.gov": ("Framingham, MA", "city"),
    "atlanta.data.socrata.com": ("Atlanta, GA", "city"),
    "data.montgomerycountymd.gov": ("Montgomery County, MD", "county"),
    "data.cityofchicago.org": ("Chicago, IL", "city"),
    "data.cityofnewyork.us": ("New York City, NY", "city"),
    "controllerdata.lacity.org": ("Los Angeles, CA", "city"),
    "www.dallasopendata.com": ("Dallas, TX", "city"),
    "dallasopendata.com": ("Dallas, TX", "city"),
    "data.austintexas.gov": ("Austin, TX", "city"),
    "data.cincinnati-oh.gov": ("Cincinnati, OH", "city"),
    "data.kcmo.org": ("Kansas City, MO", "city"),
    "data.nashville.gov": ("Nashville, TN", "city"),
    "data.sandiego.gov": ("San Diego, CA", "city"),
    "data.fultoncountyga.gov": ("Fulton County, GA", "county"),
    "data.countyofriverside.us": ("Riverside County, CA", "county"),
    "citydata.mesaaz.gov": ("Mesa, AZ", "city"),
    "data.brla.gov": ("Baton Rouge, LA", "city"),
    "data.cstx.gov": ("College Station, TX", "city"),
}


def http_get(url, retries=2, timeout=20):
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "msa-research/1.0"})
            with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"
            if e.code in (400, 403, 404):
                return None
        except Exception as e:  # noqa: BLE001
            last = str(e)
        time.sleep(0.6 * (i + 1))
    return None


def discover():
    """Enumerate candidate datasets across Socrata domains."""
    found = {}
    for term in SEARCH_TERMS:
        offset = 0
        while True:
            q = urllib.parse.urlencode({"q": term, "only": "dataset", "limit": 100, "offset": offset})
            data = http_get(f"{DISCOVERY}?{q}")
            if not data:
                break
            results = data.get("results", [])
            for r in results:
                res = r.get("resource", {})
                dom = (r.get("metadata", {}) or {}).get("domain")
                rid = res.get("id")
                name = res.get("name", "")
                if dom and rid:
                    found[(dom, rid)] = name
            offset += 100
            if offset >= min(data.get("resultSetSize", 0), 400) or not results:
                break
            time.sleep(0.15)
    print(f"  discovered {len(found)} candidate datasets", flush=True)
    return found


def pick_columns(columns):
    """Return (vendor_field, amount_field, date_field) best guesses."""
    def score(col, hints, bad=()):
        fn = (col.get("fieldName") or "").lower()
        nm = (col.get("name") or "").lower()
        text = fn + " " + nm
        if any(b in text for b in bad):
            return -1
        return sum(1 for h in hints if h in text)

    vend = max(columns, key=lambda c: score(c, VENDOR_HINTS, VENDOR_BAD), default=None)
    if not vend or score(vend, VENDOR_HINTS, VENDOR_BAD) <= 0:
        return None, None, None
    # amount: prefer numeric type
    amt_candidates = [c for c in columns if score(c, AMOUNT_HINTS) > 0]
    amt = None
    for c in sorted(amt_candidates, key=lambda c: score(c, AMOUNT_HINTS), reverse=True):
        if (c.get("dataTypeName") or "") in ("number", "money", "double", "amount"):
            amt = c
            break
    if not amt and amt_candidates:
        amt = amt_candidates[0]
    date = None
    for c in columns:
        if (c.get("dataTypeName") or "") == "calendar_date":
            date = c
            break
    if not date:
        dcs = [c for c in columns if any(h in ((c.get("fieldName") or "") + (c.get("name") or "")).lower() for h in DATE_HINTS)]
        date = dcs[0] if dcs else None
    return (vend.get("fieldName"), amt.get("fieldName") if amt else None,
            date.get("fieldName") if date else None)


def query_dataset(domain, rid, vfield, afield, dfield):
    where = " OR ".join([f"upper(`{vfield}`) like '%{m}%'" for m in MATCH])
    sel = f"`{vfield}`"
    if afield:
        sel += f",`{afield}`"
    if dfield:
        sel += f",`{dfield}`"
    params = urllib.parse.urlencode({"$select": sel, "$where": where, "$limit": 50000})
    url = f"https://{domain}/resource/{rid}.json?{params}"
    rows = http_get(url)
    if rows is None:
        # retry without $select (some datasets reject backticked select)
        params = urllib.parse.urlencode({"$where": where, "$limit": 50000})
        rows = http_get(f"https://{domain}/resource/{rid}.json?{params}")
    return rows if isinstance(rows, list) else None


def to_float(v):
    try:
        return float(str(v).replace("$", "").replace(",", "").strip() or 0)
    except ValueError:
        return 0.0


def main():
    import sys
    os.makedirs(RAW, exist_ok=True)
    os.makedirs(PROC, exist_ok=True)

    if "--reprocess" in sys.argv:
        # Re-clean & re-aggregate from the saved raw sweep (no network).
        with open(os.path.join(RAW, "socrata_hits.json")) as f:
            hits = json.load(f)
        print(f"== Reprocessing {len(hits)} saved rows ==")
        write_outputs(hits)
        return

    print("== Discovering datasets ==")
    datasets = discover()

    hits = []
    n = len(datasets)
    progress = {"done": 0}
    lock = threading.Lock()

    def probe(item):
        (domain, rid), name = item
        out = []
        meta = http_get(f"https://{domain}/api/views/{rid}.json")
        if meta and "columns" in meta:
            vfield, afield, dfield = pick_columns(meta["columns"])
            if vfield:
                rows = query_dataset(domain, rid, vfield, afield, dfield)
                if rows:
                    label, level = DOMAIN_LABEL.get(domain, (domain, "local"))
                    for row in rows:
                        out.append({
                            "domain": domain, "jurisdiction": label, "level": level,
                            "dataset": name, "dataset_id": rid,
                            "vendor": row.get(vfield, ""),
                            "amount": to_float(row.get(afield)) if afield else 0.0,
                            "date": row.get(dfield, "") if dfield else "",
                        })
                    print(f"  HIT {label} ({domain}) — {len(rows)} rows  [{name[:40]}]", flush=True)
        with lock:
            progress["done"] += 1
            if progress["done"] % 50 == 0:
                print(f"  ...probed {progress['done']}/{n}, {len(hits)} hits", flush=True)
        return out

    with ThreadPoolExecutor(max_workers=16) as ex:
        for fut in as_completed([ex.submit(probe, it) for it in datasets.items()]):
            hits.extend(fut.result())

    with open(os.path.join(RAW, "socrata_hits.json"), "w") as f:
        json.dump(hits, f, indent=2)
    print(f"\nTotal matched payment rows: {len(hits)}")
    write_outputs(hits)


def write_outputs(hits):
    # Clean: keep only true MSA entities, real payments (amount > 0), non-demo domains.
    # Re-derive jurisdiction label/level from DOMAIN_LABEL so reprocessing applies new labels.
    cleaned = []
    for h in hits:
        if excluded_domain(h["domain"]) or not is_real_msa(h.get("vendor")):
            continue
        if to_float(h.get("amount")) <= 0:
            continue
        label, level = DOMAIN_LABEL.get(h["domain"], (h["domain"], "local"))
        h = dict(h, jurisdiction=label, level=level)
        cleaned.append(h)
    print(f"  cleaned: {len(cleaned)} of {len(hits)} rows kept", flush=True)
    hits = cleaned

    # CSV
    csv_path = os.path.join(PROC, "state_local.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["jurisdiction", "level", "domain", "vendor",
                                          "amount", "date", "dataset"])
        w.writeheader()
        for h in hits:
            w.writerow({k: h.get(k, "") for k in w.fieldnames})

    # aggregate by jurisdiction
    agg = collections.defaultdict(lambda: {"amount": 0.0, "count": 0, "level": "local",
                                           "domain": "", "vendors": set(), "datasets": set()})
    for h in hits:
        a = agg[h["jurisdiction"]]
        a["amount"] += h["amount"]
        a["count"] += 1
        a["level"] = h["level"]
        a["domain"] = h["domain"]
        a["vendors"].add(h["vendor"])
        a["datasets"].add(h["dataset"])
    by_juris = [{
        "jurisdiction": k, "level": v["level"], "domain": v["domain"],
        "amount": round(v["amount"], 2), "count": v["count"],
        "vendor_variants": sorted(x for x in v["vendors"] if x)[:6],
    } for k, v in agg.items()]
    by_juris.sort(key=lambda x: x["amount"], reverse=True)

    total = sum(h["amount"] for h in hits)
    out = {
        "meta": {
            "total_payments_usd": round(total, 2),
            "total_rows": len(hits),
            "n_jurisdictions": len(by_juris),
            "source": "Socrata government open-data checkbooks (states, counties, cities)",
            "match_terms": MATCH,
        },
        "by_jurisdiction": by_juris,
    }
    with open(os.path.join(PROC, "state_local.json"), "w") as f:
        json.dump(out, f, indent=2)
    print(f"Wrote {csv_path}")
    print(f"Jurisdictions with MSA payments: {len(by_juris)} · total ${total:,.0f}")
    for j in by_juris[:15]:
        print(f"  {j['level']:6s} {j['jurisdiction'][:34]:34s} ${j['amount']:>12,.0f}  ({j['count']})")


if __name__ == "__main__":
    main()
