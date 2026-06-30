#!/usr/bin/env python3
"""
TIER-1 municipal fire-procurement sweep (free, public open-data only).

Sweeps Socrata-hosted government CONTRACT-AWARD / PURCHASE-ORDER / checkbook datasets for
FIRE-segment procurement (SCBA, turnout/bunker gear, fire helmets) and attributes each hit to:
  - MSA (direct or via product spec e.g. "MSA G1", "Globe", "Cairns")
  - an MSA authorized DEALER (Witmer, Casco, MacQueen, ...)
  - a COMPETITOR (Scott/Air-Pak, Draeger, LION, Morning Pride, Fire-Dex, ...)
  - fire-unattributed (a fire-PPE buy whose vendor we can't classify)

Goal: show MSA's share of the *visible* municipal fire-equipment spend, the piece the federal
data misses. Detection is OUT of scope.

Outputs:
  data/raw/municipal_hits.json
  data/processed/municipal.csv
  data/processed/municipal.json   (aggregates for the site)
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

# Discovery search terms — datasets that hold awards / POs / spend (where fire gear shows up).
SEARCH_TERMS = ["contract awards", "purchase orders", "checkbook", "vendor payments",
                "expenditures", "contracts", "spending"]

# --- Fire PRODUCT terms (searched in description/title/commodity columns) ---
# Specific to firefighter PPE; deliberately NO bare "fire" (matches alarms/sprinklers/stations).
FIRE_PRODUCT = ["SCBA", "SELF-CONTAINED BREATHING", "SELF CONTAINED BREATHING", "BREATHING APPARATUS",
                "AIR PACK", "AIRPACK", "AIR MASK", "TURNOUT GEAR", "TURNOUT COAT", "BUNKER GEAR",
                "FIREFIGHTER PROTECTIVE", "FIRE HELMET", "FIREFIGHTING APPARATUS",
                "PASS DEVICE", "AIR CYLINDER"]

# --- Vendor / brand attribution terms ---
MSA_VENDOR = ["MINE SAFETY", "MSA SAFETY", "MSA INC", "MSA, INC"]
MSA_PRODUCT = ["MSA G1", "G1 SCBA", "FIREHAWK", "AIRHAWK", "GLOBE TURNOUT", "CAIRNS", "MSA LUNAR"]
DEALERS = ["WITMER", "THEFIRESTORE", "CASCO INDUSTRIES", "MACQUEEN", "VOGELPOHL",
           "SENTINEL EMERGENCY", "SUNBELT FIRE", "FIREMATIC", "TEN-8", "TEN 8",
           "MUNICIPAL EMERGENCY SERVICES", "FIRE SAFETY USA"]
COMPETITORS = ["AIR-PAK", "AIR PAK", "SCOTT SAFETY", "SCOTT FIRE", "DRAEGER", "DRAGER", "DRAGERWERK",
               "LION APPAREL", "LION GROUP", "MORNING PRIDE", "SURVIVAIR", "FIRE-DEX", "FIRE DEX",
               "VERIDIAN", "GLOBE MANUFACTURING"]

# Terms to actually push to the server-side $where (vendor OR description).
DESC_TERMS = FIRE_PRODUCT + MSA_PRODUCT
VENDOR_TERMS = MSA_VENDOR + DEALERS + COMPETITORS

# Non-fire MSA products to exclude (MSA also sells these; out of scope for fire segment).
NON_FIRE = ["BODY ARMOR", "BALLISTIC", "BULLET", "AMMUNITION", "GAS DETECT", "GAS MONITOR",
            "DETECTOR", "ALTAIR", "MULTIGAS", "MULTI-GAS", "CALIBRATION GAS", "HARD HAT", "V-GARD"]
# Non-US domains seen in the Socrata catalog — fire scope is U.S. only.
NON_US_SUBSTR = [".ca", ".au", "novascotia", "ontario", "alberta", "canada", ".uk", "queensland"]
MAX_SANE_AMOUNT = 5e8  # a single municipal fire PO/contract above this is a data error

VENDOR_HINTS = ["vendor", "payee", "supplier", "merchant", "company", "recipient", "legal_name", "contractor"]
VENDOR_BAD = ["number", "id", "code", "type", "city", "state", "zip", "address", "dept", "department"]
DESC_HINTS = ["description", "title", "short_title", "item", "commodity", "purpose", "purchase",
              "detail", "scope", "award", "service"]
AMOUNT_HINTS = ["amount", "amt", "paid", "payment", "check", "total", "expended", "value", "contract_amount", "award"]
DATE_HINTS = ["date", "ending", "fiscal", "year", "start", "posted", "award"]
AGENCY_HINTS = ["agency", "department", "dept", "entity", "office", "buyer"]

EXCLUDE_DOMAIN_SUBSTR = ["demo.socrata.com", "sandbox", ".test.", "test.socrata"]

DOMAIN_LABEL = {
    "data.cityofnewyork.us": ("New York City, NY", "city"),
    "data.cityofchicago.org": ("Chicago, IL", "city"),
    "controllerdata.lacity.org": ("Los Angeles, CA", "city"),
    "data.brla.gov": ("Baton Rouge, LA", "city"),
    "data.nashville.gov": ("Nashville, TN", "city"),
    "data.sandiego.gov": ("San Diego, CA", "city"),
    "data.austintexas.gov": ("Austin, TX", "city"),
    "data.kcmo.org": ("Kansas City, MO", "city"),
    "data.cincinnati-oh.gov": ("Cincinnati, OH", "city"),
    "data.ny.gov": ("New York State", "state"),
    "data.ct.gov": ("Connecticut", "state"),
    "data.texas.gov": ("Texas", "state"),
    "data.wa.gov": ("Washington", "state"),
    "data.nj.gov": ("New Jersey", "state"),
    "opendata.maryland.gov": ("Maryland", "state"),
}

# Curated high-value award/PO datasets to always probe (domain, dataset_id).
SEED_DATASETS = [
    ("data.cityofnewyork.us", "qyyg-4tf5"),  # NYC Recent Contract Awards
    ("data.cityofnewyork.us", "mdcw-n682"),  # NYC Active Contracts
    ("data.cityofchicago.org", "rsxa-ify5"),  # Chicago Contracts
    ("controllerdata.lacity.org", "5ru3-n8sy"),  # LA Purchase Orders / Invoices
    ("data.brla.gov", "2ung-w7t4"),  # Baton Rouge POs & Contracts
]


def http_get(url, retries=2, timeout=25):
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
                if dom and rid and not any(s in dom for s in EXCLUDE_DOMAIN_SUBSTR):
                    found[(dom, rid)] = res.get("name", "")
            offset += 100
            if offset >= min(data.get("resultSetSize", 0), 300) or not results:
                break
            time.sleep(0.1)
    for d in SEED_DATASETS:
        found.setdefault(d, "(seed)")
    print(f"  discovered {len(found)} candidate datasets", flush=True)
    return found


def pick(columns, hints, bad=(), require_type=None):
    def score(c):
        t = ((c.get("fieldName") or "") + " " + (c.get("name") or "")).lower()
        if any(b in t for b in bad):
            return -1
        return sum(1 for h in hints if h in t)
    best = max(columns, key=score, default=None)
    if not best or score(best) <= 0:
        return None
    return best.get("fieldName")


def detect_cols(columns):
    vendor = pick(columns, VENDOR_HINTS, VENDOR_BAD)
    amount = None
    for c in sorted(columns, key=lambda c: sum(1 for h in AMOUNT_HINTS if h in ((c.get("fieldName") or "")+(c.get("name") or "")).lower()), reverse=True):
        t = ((c.get("fieldName") or "")+(c.get("name") or "")).lower()
        if any(h in t for h in AMOUNT_HINTS):
            amount = c.get("fieldName")
            if (c.get("dataTypeName") or "") in ("number", "money", "double"):
                break
    desc = pick(columns, DESC_HINTS)
    agency = pick(columns, AGENCY_HINTS)
    date = None
    for c in columns:
        if (c.get("dataTypeName") or "") == "calendar_date":
            date = c.get("fieldName"); break
    if not date:
        date = pick(columns, DATE_HINTS)
    return vendor, amount, desc, agency, date


def build_where(vendor, desc):
    clauses = []
    if desc:
        for t in DESC_TERMS:
            clauses.append(f"upper(`{desc}`) like '%{t}%'")
    if vendor:
        for t in VENDOR_TERMS:
            clauses.append(f"upper(`{vendor}`) like '%{t}%'")
    return " OR ".join(clauses)


def query(domain, rid, where):
    params = urllib.parse.urlencode({"$where": where, "$limit": 8000})
    return http_get(f"https://{domain}/resource/{rid}.json?{params}")


def to_float(v):
    try:
        return float(str(v).replace("$", "").replace(",", "").strip() or 0)
    except ValueError:
        return 0.0


def classify(vendor, desc):
    """First-pass class used during the sweep (kept broad; cleaned later)."""
    v = (vendor or "").upper()
    d = (desc or "").upper()
    blob = v + " " + d
    if any(t in v for t in MSA_VENDOR) or any(t in d for t in MSA_PRODUCT):
        return "MSA (direct or spec'd)"
    if any(t in v for t in DEALERS):
        return "MSA dealer (likely)"
    if any(t in blob for t in COMPETITORS):
        return "Competitor"
    if any(t in d for t in FIRE_PRODUCT):
        return "Fire — unattributed"
    return "Other"


def clean_classify(vendor, desc):
    """Refined class used on the saved rows. Returns None to DROP the row."""
    v = (vendor or "").upper()
    d = (desc or "").upper()
    is_fire = any(t in d for t in FIRE_PRODUCT) or any(t in d for t in MSA_PRODUCT)
    is_nonfire = any(t in d for t in NON_FIRE)
    if any(t in v for t in MSA_VENDOR):
        if is_nonfire and not is_fire:
            return None                      # MSA body armor / gas detection — drop (not fire)
        return "MSA direct"                  # MSA by name (fire-confirmed or PO line w/o detail)
    if any(t in d for t in MSA_PRODUCT):
        return "MSA product spec'd"          # e.g. "MSA G1", "Globe", "Cairns" in the spec
    if any(t in v for t in DEALERS):
        return "Via MSA fire dealer"         # dedicated fire dealer that carries MSA (multi-brand)
    if any(t in (v + " " + d) for t in COMPETITORS):
        return "Competitor"
    if is_fire and not is_nonfire:
        return "Fire — unattributed"
    return None


def main():
    import sys
    os.makedirs(RAW, exist_ok=True)
    os.makedirs(PROC, exist_ok=True)

    if "--reprocess" in sys.argv:
        with open(os.path.join(RAW, "municipal_hits.json")) as f:
            hits = json.load(f)
        print(f"== Reprocessing {len(hits)} saved rows ==")
        write_outputs(hits)
        return

    print("== Discovering award/PO datasets ==")
    datasets = discover()
    hits = []
    n = len(datasets)
    prog = {"d": 0}
    lock = threading.Lock()

    def probe(item):
        (domain, rid), name = item
        out = []
        meta = http_get(f"https://{domain}/api/views/{rid}.json")
        if meta and "columns" in meta:
            vendor, amount, desc, agency, date = detect_cols(meta["columns"])
            where = build_where(vendor, desc)
            if where:
                rows = query(domain, rid, where)
                if isinstance(rows, list) and rows:
                    label, level = DOMAIN_LABEL.get(domain, (domain, "local"))
                    for row in rows:
                        vn = row.get(vendor, "") if vendor else ""
                        ds = row.get(desc, "") if desc else ""
                        cls = classify(vn, ds)
                        if cls == "Other":
                            continue
                        out.append({
                            "domain": domain, "jurisdiction": label, "level": level,
                            "dataset": name, "vendor": vn, "amount": to_float(row.get(amount)) if amount else 0.0,
                            "date": row.get(date, "") if date else "",
                            "agency": row.get(agency, "") if agency else "",
                            "description": (ds or "")[:200], "class": cls,
                        })
                    if out:
                        print(f"  HIT {label} ({domain}) — {len(out)} fire rows [{name[:34]}]", flush=True)
        with lock:
            prog["d"] += 1
            if prog["d"] % 50 == 0:
                print(f"  ...probed {prog['d']}/{n}, {len(hits)} hits", flush=True)
        return out

    with ThreadPoolExecutor(max_workers=16) as ex:
        for fut in as_completed([ex.submit(probe, it) for it in datasets.items()]):
            hits.extend(fut.result())

    with open(os.path.join(RAW, "municipal_hits.json"), "w") as f:
        json.dump(hits, f, indent=2)
    print(f"\nTotal fire-related rows: {len(hits)}")
    write_outputs(hits)


def clean(hits):
    """US-only, sane amounts, refined classification. Returns cleaned rows."""
    out = []
    for h in hits:
        if any(s in h["domain"] for s in NON_US_SUBSTR):
            continue
        amt = to_float(h.get("amount"))
        if amt <= 0 or amt > MAX_SANE_AMOUNT:
            # keep zero/over-cap rows out of $ totals, but a bad amount alone shouldn't drop a real fire row;
            # only drop the over-cap garbage. Zero-amount rows are dropped from $ view.
            if amt > MAX_SANE_AMOUNT or amt <= 0:
                continue
        cls = clean_classify(h.get("vendor"), h.get("description"))
        if cls is None:
            continue
        out.append(dict(h, amount=amt, **{"class": cls}))
    return out


def write_outputs(hits):
    hits = clean(hits)
    print(f"  cleaned -> {len(hits)} rows kept", flush=True)
    with open(os.path.join(PROC, "municipal.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["jurisdiction", "level", "class", "vendor", "amount",
                                          "date", "agency", "description", "domain", "dataset"])
        w.writeheader()
        for h in hits:
            w.writerow({k: h.get(k, "") for k in w.fieldnames})

    by_class = collections.defaultdict(lambda: {"amount": 0.0, "count": 0})
    by_juris = collections.defaultdict(lambda: {"amount": 0.0, "count": 0, "level": "local", "classes": collections.Counter()})
    for h in hits:
        c = h["class"]
        by_class[c]["amount"] += h["amount"]; by_class[c]["count"] += 1
        j = by_juris[h["jurisdiction"]]
        j["amount"] += h["amount"]; j["count"] += 1; j["level"] = h["level"]; j["classes"][c] += 1

    out = {
        "meta": {
            "total_rows": len(hits),
            "n_jurisdictions": len(by_juris),
            "source": "Municipal/state open-data (Socrata) contract-award & PO datasets",
            "scope": "Fire segment only (SCBA, turnout, helmets). Vendor + product attribution.",
        },
        "by_class": [{"class": k, "amount": round(v["amount"], 2), "count": v["count"]}
                     for k, v in sorted(by_class.items(), key=lambda x: -x[1]["amount"])],
        "by_jurisdiction": sorted([
            {"jurisdiction": k, "level": v["level"], "amount": round(v["amount"], 2),
             "count": v["count"], "classes": dict(v["classes"])}
            for k, v in by_juris.items()], key=lambda x: -x["amount"]),
    }
    with open(os.path.join(PROC, "municipal.json"), "w") as f:
        json.dump(out, f, indent=2)
    print("\n=== by class ===")
    for c in out["by_class"]:
        print(f"  {c['class']:26s} ${c['amount']:>12,.0f}  ({c['count']})")
    print(f"\nJurisdictions: {len(by_juris)}")
    for j in out["by_jurisdiction"][:12]:
        print(f"  {j['level']:6s} {j['jurisdiction'][:30]:30s} ${j['amount']:>11,.0f}  ({j['count']})")


if __name__ == "__main__":
    main()
