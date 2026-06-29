#!/usr/bin/env python3
"""
Collect MSA Safety federal procurement data from the USAspending.gov API.

Outputs:
  data/raw/awards_prime.json     - verbatim paginated award rows
  data/raw/award_details/*.json  - per-award detail (NAICS, PSC, geography, description)
  data/processed/awards.csv      - normalized, analysis-ready table

Re-runnable: safe to run repeatedly; overwrites outputs. No manual data entry.
"""
import json
import time
import csv
import os
import sys
import urllib.request
import urllib.error
import urllib.parse
import ssl

try:
    import certifi
    SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:  # noqa: BLE001
    SSL_CTX = ssl.create_default_context()
    SSL_CTX.check_hostname = False
    SSL_CTX.verify_mode = ssl.CERT_NONE

API = "https://api.usaspending.gov/api/v2"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
PROC = os.path.join(ROOT, "data", "processed")
DETAIL_DIR = os.path.join(RAW, "award_details")

# MSA legal entities as they appear in federal data.
RECIPIENT_NAMES = [
    "MSA SAFETY SALES, LLC",
    "MSA SAFETY INCORPORATED",
    "MINE SAFETY APPLIANCES COMPANY",
    "MINE SAFETY APPLIANCES COMPANY, LLC",
]

START_DATE = "2021-01-01"
END_DATE = "2026-06-30"
# Contract award type codes (A=BPA call/Delivery, B=Purchase Order, C=Delivery Order, D=Definitive Contract)
AWARD_TYPE_CODES = ["A", "B", "C", "D"]


def post(path, payload, retries=4):
    url = f"{API}{path}"
    data = json.dumps(payload).encode()
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url, data=data, headers={"Content-Type": "application/json"}, method="POST"
            )
            with urllib.request.urlopen(req, timeout=60, context=SSL_CTX) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            last_err = f"HTTP {e.code}: {e.read().decode()[:300]}"
        except Exception as e:  # noqa: BLE001
            last_err = str(e)
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"POST {path} failed after {retries} tries: {last_err}")


def get(path, retries=4):
    url = f"{API}{path}"
    last_err = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=60, context=SSL_CTX) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            last_err = f"HTTP {e.code}: {e.read().decode()[:300]}"
        except Exception as e:  # noqa: BLE001
            last_err = str(e)
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"GET {path} failed after {retries} tries: {last_err}")


def fetch_prime_awards():
    """Page through spending_by_award for all MSA recipient names."""
    fields = [
        "Award ID", "Recipient Name", "Award Amount", "Total Outlays",
        "Description", "Awarding Agency", "Awarding Sub Agency",
        "Start Date", "End Date", "Award Type", "Contract Award Type",
        "recipient_id", "generated_internal_id",
    ]
    all_rows = {}
    for name in RECIPIENT_NAMES:
        page = 1
        while True:
            payload = {
                "filters": {
                    "recipient_search_text": [name],
                    "time_period": [{"start_date": START_DATE, "end_date": END_DATE}],
                    "award_type_codes": AWARD_TYPE_CODES,
                },
                "fields": fields,
                "page": page,
                "limit": 100,
                "sort": "Award Amount",
                "order": "desc",
            }
            resp = post("/search/spending_by_award/", payload)
            results = resp.get("results", [])
            for row in results:
                # Keep exact-match recipients only (search is fuzzy).
                gid = row.get("generated_internal_id")
                if gid:
                    all_rows[gid] = row
            print(f"  [{name}] page {page}: +{len(results)} (total unique {len(all_rows)})")
            if not resp.get("page_metadata", {}).get("hasNext"):
                break
            page += 1
            time.sleep(0.3)
    return list(all_rows.values())


def fetch_award_detail(generated_internal_id):
    safe = generated_internal_id.replace("/", "_")
    path = os.path.join(DETAIL_DIR, f"{safe}.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    detail = get(f"/awards/{urllib.parse.quote(generated_internal_id, safe='')}/")
    with open(path, "w") as f:
        json.dump(detail, f, indent=2)
    time.sleep(0.2)
    return detail


def main():
    os.makedirs(RAW, exist_ok=True)
    os.makedirs(PROC, exist_ok=True)
    os.makedirs(DETAIL_DIR, exist_ok=True)

    print("== Fetching prime award list ==")
    rows = fetch_prime_awards()
    with open(os.path.join(RAW, "awards_prime.json"), "w") as f:
        json.dump(rows, f, indent=2)
    print(f"Saved {len(rows)} prime awards.")

    print("== Fetching per-award detail ==")
    details = []
    for i, row in enumerate(rows, 1):
        gid = row.get("generated_internal_id")
        try:
            d = fetch_award_detail(gid)
            details.append(d)
        except Exception as e:  # noqa: BLE001
            print(f"  ! detail failed for {gid}: {e}")
        if i % 20 == 0:
            print(f"  ...{i}/{len(rows)} details")

    print("== Writing normalized CSV ==")
    write_csv(rows, details)
    print("Done.")


def _g(d, *keys, default=""):
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
        if cur is None:
            return default
    return cur


def write_csv(rows, details):
    by_id = {}
    for d in details:
        gid = d.get("generated_unique_award_id") or _g(d, "generated_internal_id")
        if gid:
            by_id[gid] = d

    out = os.path.join(PROC, "awards.csv")
    cols = [
        "award_id", "generated_internal_id", "recipient_name", "recipient_uei",
        "award_amount", "total_obligation", "potential_total_value",
        "start_date", "end_date", "award_type",
        "awarding_agency", "awarding_sub_agency", "funding_agency",
        "naics_code", "naics_description",
        "psc_code", "psc_description",
        "pop_state", "pop_city", "pop_country",
        "number_of_offers", "extent_competed",
        "description",
    ]
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for row in rows:
            gid = row.get("generated_internal_id")
            d = by_id.get(gid, {})
            w.writerow({
                "award_id": row.get("Award ID", ""),
                "generated_internal_id": gid,
                "recipient_name": row.get("Recipient Name", ""),
                "recipient_uei": _g(d, "recipient", "recipient_hash") or _g(d, "recipient", "recipient_uei"),
                "award_amount": row.get("Award Amount", ""),
                "total_obligation": _g(d, "total_obligation", default=row.get("Award Amount", "")),
                "potential_total_value": _g(d, "base_and_all_options_value"),
                "start_date": row.get("Start Date", ""),
                "end_date": row.get("End Date", ""),
                "award_type": row.get("Contract Award Type") or row.get("Award Type", ""),
                "awarding_agency": row.get("Awarding Agency", ""),
                "awarding_sub_agency": row.get("Awarding Sub Agency", ""),
                "funding_agency": _g(d, "funding_agency", "toptier_agency", "name"),
                "naics_code": _g(d, "naics_hierarchy", "base_code", "code") or _g(d, "naics", "code"),
                "naics_description": _g(d, "naics_hierarchy", "base_code", "description") or _g(d, "naics", "description"),
                "psc_code": _g(d, "psc_hierarchy", "base_code", "code") or _g(d, "psc", "code"),
                "psc_description": _g(d, "psc_hierarchy", "base_code", "description") or _g(d, "psc", "description"),
                "pop_state": _g(d, "place_of_performance", "state_code"),
                "pop_city": _g(d, "place_of_performance", "city_name"),
                "pop_country": _g(d, "place_of_performance", "country_name"),
                "number_of_offers": _g(d, "latest_transaction_contract_data", "number_of_offers_received"),
                "extent_competed": _g(d, "latest_transaction_contract_data", "extent_competed"),
                "description": (row.get("Description") or _g(d, "description") or "").replace("\n", " ").strip(),
            })
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
