"""Create the Stunt Double VM on Vultr via the Vultr API (stdlib only).

  VULTR_API_KEY=... VULTR_INFERENCE_KEY=... python3 infra/provision.py [--region sjc] [--plan vc2-2c-4gb]

The VM bootstraps itself with cloud-init (infra/setup-vultr.sh) and then pull-deploys from GitHub.
"""
import argparse
import base64
import json
import os
import pathlib
import time
import urllib.request

API = "https://api.vultr.com/v2"


def call(method: str, path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body else None,  # noqa: S310 - fixed https API base
                                 headers={"Authorization": f"Bearer {os.environ['VULTR_API_KEY']}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310
        raw = r.read()
        return json.loads(raw) if raw else {}


def object_storage(region: str, label: str) -> dict:
    """Create (or reuse) a Vultr Object Storage subscription near the VM. UNTESTED until a Vultr API key is available."""
    existing = [o for o in call("GET", "/object-storage?per_page=100").get("object_storages", []) if o.get("label") == f"{label}-evidence"]
    if existing:
        obj = existing[0]
    else:
        clusters = call("GET", "/object-storage/clusters?per_page=100")["clusters"]
        cluster = next((c for c in clusters if c.get("region") == region and c.get("deploy") == "yes"), None) or next(c for c in clusters if c.get("deploy") == "yes")
        body = {"cluster_id": cluster["id"], "label": f"{label}-evidence"}
        try:
            tiers = call("GET", f"/object-storage/clusters/{cluster['id']}/tiers").get("tiers", [])
            if tiers:
                body["tier_id"] = sorted(tiers, key=lambda t: float(t.get("price", 0) or 0))[0]["id"]
        except Exception as e:  # noqa: BLE001 - older API without tiers
            print(f"(no tier list: {e}); creating with the cluster default")
        obj = call("POST", "/object-storage", body)["object_storage"]
        print(f"Created Object Storage {obj['id']} in cluster {cluster['hostname']}; waiting for it to be active...")
    while obj.get("status") != "active":
        time.sleep(10)
        obj = call("GET", f"/object-storage/{obj['id']}")["object_storage"]
    return obj


def credit_check(plan: str, max_monthly_usd: float, extra_monthly_usd: float = 0.0) -> None:
    """Refuse to spend unless the remaining Vultr credit covers it: the linked card must never be charged.

    Vultr reports `balance` negative when the account holds credit; `pending_charges` is this month's usage so far.
    """
    acct = call("GET", "/account")["account"]
    credit = -float(acct.get("balance", 0)) - float(acct.get("pending_charges", 0))
    plans = {p["id"]: p for p in call("GET", "/plans?per_page=500").get("plans", [])}
    if plan not in plans:
        raise SystemExit(f"Unknown plan {plan!r}")
    monthly = float(plans[plan]["monthly_cost"]) + extra_monthly_usd
    print(f"Credit left: ${credit:,.2f} · this setup: ${monthly:,.2f}/month at most (limit ${max_monthly_usd:,.2f})")
    if monthly > max_monthly_usd:
        raise SystemExit(f"Refusing: ${monthly:,.2f}/month is above the ${max_monthly_usd:,.2f} limit. Pick a smaller plan or raise --max-monthly.")
    if monthly > credit:
        raise SystemExit(f"Refusing: a full month (${monthly:,.2f}) is more than the remaining credit (${credit:,.2f}). The card would pay.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default="sjc")
    ap.add_argument("--plan", default="vc2-2c-4gb")
    ap.add_argument("--label", default="stunt-double")
    ap.add_argument("--object-storage", action="store_true", help="also create Vultr Object Storage for the evidence archive")
    ap.add_argument("--max-monthly", type=float, default=30.0, help="refuse anything costing more than this per month (USD)")
    a = ap.parse_args()
    credit_check(a.plan, a.max_monthly, extra_monthly_usd=6.0 if a.object_storage else 0.0)
    s3 = object_storage(a.region, a.label) if a.object_storage else None

    existing = [i for i in call("GET", "/instances?per_page=100").get("instances", []) if i["label"] == a.label]
    if existing:
        inst = existing[0]
        print(f"Instance already exists: {inst['id']} {inst['main_ip']} ({inst['status']})")
    else:
        os_id = next(o["id"] for o in call("GET", "/os?per_page=500")["os"] if o["name"].startswith("Ubuntu 24.04") and "x64" in o["name"])
        script = (pathlib.Path(__file__).parent / "setup-vultr.sh").read_text()
        key = os.environ.get("VULTR_INFERENCE_KEY", "")
        exports = (f"export VULTR_INFERENCE_KEY='{key}'\n" if key else "")
        if s3:
            exports += f"export SD_S3_ENDPOINT='https://{s3['s3_hostname']}' SD_S3_ACCESS_KEY='{s3['s3_access_key']}' SD_S3_SECRET_KEY='{s3['s3_secret_key']}'\n"
        user_data = "#!/usr/bin/env bash\n" + exports + script.split("\n", 1)[1]
        inst = call("POST", "/instances", {"region": a.region, "plan": a.plan, "os_id": os_id, "label": a.label, "hostname": a.label,
                                           "user_data": base64.b64encode(user_data.encode()).decode(), "backups": "disabled",
                                           "tags": ["stunt-double", "agent-rush"]})["instance"]
        print(f"Created instance {inst['id']} in {a.region} ({a.plan}); waiting for an IP...")
    no_ip = (None, "", "0.0.0.0")  # noqa: S104 - "no IP assigned yet", not a bind address
    while inst.get("main_ip") in no_ip or inst.get("status") != "active":
        time.sleep(10)
        inst = call("GET", f"/instances/{inst['id']}")["instance"]
    host = inst["main_ip"].replace(".", "-") + ".sslip.io"
    print(json.dumps({"id": inst["id"], "ip": inst["main_ip"], "url": f"https://{host}", "status": inst["status"]}, indent=2))
    print("Cloud-init setup takes ~5-8 minutes after the VM is active.")


if __name__ == "__main__":
    main()
