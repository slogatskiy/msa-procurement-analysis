#!/usr/bin/env python3
"""
Pull FEMA Assistance to Firefighters Grants (AFG) volume as an SCBA-demand proxy.

AFG (CFDA/Assistance Listing 97.044) is federal grant money paid DIRECTLY to fire
departments to buy equipment -- prominently SCBA. Departments use it to replace gear that
regulations bar them from running once it is >2 NFPA generations old. So national AFG
volume is a leading indicator of fire-department SCBA purchasing (i.e. MSA demand).

Outputs: data/processed/afg.json
"""
import json
import os
import time
import urllib.request
import urllib.error
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
PROC = os.path.join(ROOT, "data", "processed")
GENERATED = "2026-06-29"

AFG_PROGRAM = "97.044"  # Assistance Listing number for AFG
GRANT_TYPES = ["02", "03", "04", "05"]  # block/formula/project/other grants


def post(path, payload, retries=4):
    data = json.dumps(payload).encode()
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(f"{API}{path}", data=data,
                                         headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=60, context=SSL_CTX) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}: {e.read().decode()[:200]}"
        except Exception as e:  # noqa: BLE001
            last = str(e)
        time.sleep(2 * (i + 1))
    raise RuntimeError(f"{path} failed: {last}")


def by_year():
    resp = post("/search/spending_over_time/", {
        "group": "fiscal_year",
        "filters": {
            "program_numbers": [AFG_PROGRAM],
            "time_period": [{"start_date": "2020-10-01", "end_date": "2026-06-30"}],
            "award_type_codes": GRANT_TYPES,
        },
    })
    out = []
    for r in resp.get("results", []):
        out.append({"fiscal_year": r["time_period"]["fiscal_year"],
                    "amount": round(r.get("aggregated_amount", 0) or 0, 2)})
    out.sort(key=lambda x: x["fiscal_year"])
    return out


def top_recipients():
    resp = post("/search/spending_by_category/recipient", {
        "category": "recipient",
        "filters": {
            "program_numbers": [AFG_PROGRAM],
            "time_period": [{"start_date": "2020-10-01", "end_date": "2026-06-30"}],
            "award_type_codes": GRANT_TYPES,
        },
        "limit": 15,
    })
    return [{"name": r.get("name"), "amount": round(r.get("amount", 0) or 0, 2)}
            for r in resp.get("results", [])]


def main():
    os.makedirs(PROC, exist_ok=True)
    years = by_year()
    try:
        recips = top_recipients()
    except Exception as e:  # noqa: BLE001
        print(f"  (top recipients skipped: {e})")
        recips = []
    total = sum(y["amount"] for y in years)
    data = {
        "meta": {
            "generated": GENERATED,
            "program": AFG_PROGRAM,
            "program_name": "FEMA Assistance to Firefighters Grants (AFG)",
            "source": "USAspending.gov API (assistance awards, Assistance Listing 97.044)",
            "total_fy21_to_present": round(total, 2),
        },
        "by_year": years,
        "top_recipients": recips,
    }
    with open(os.path.join(PROC, "afg.json"), "w") as f:
        json.dump(data, f, indent=2)
    print(f"Wrote {os.path.join(PROC, 'afg.json')}")
    print(f"AFG total FY21->present: ${total:,.0f}")
    for y in years:
        print(f"  FY{y['fiscal_year']}: ${y['amount']:,.0f}")


if __name__ == "__main__":
    main()
