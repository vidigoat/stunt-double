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
    req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body else None,
                                 headers={"Authorization": f"Bearer {os.environ['VULTR_API_KEY']}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
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
        except Exception:  # noqa: BLE001 - older API without tiers
            pass
        obj = call("POST", "/object-storage", body)["object_storage"]
        print(f"Created Object Storage {obj['id']} in cluster {cluster['hostname']}; waiting for it to be active...")
    while obj.get("status") != "active":
        time.sleep(10)
        obj = call("GET", f"/object-storage/{obj['id']}")["object_storage"]
    return obj


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default="sjc")
    ap.add_argument("--plan", default="vc2-2c-4gb")
    ap.add_argument("--label", default="stunt-double")
    ap.add_argument("--object-storage", action="store_true", help="also create Vultr Object Storage for the evidence archive")
    a = ap.parse_args()
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
    while inst.get("main_ip") in (None, "", "0.0.0.0") or inst.get("status") != "active":
        time.sleep(10)
        inst = call("GET", f"/instances/{inst['id']}")["instance"]
    host = inst["main_ip"].replace(".", "-") + ".sslip.io"
    print(json.dumps({"id": inst["id"], "ip": inst["main_ip"], "url": f"https://{host}", "status": inst["status"]}, indent=2))
    print("Cloud-init setup takes ~5-8 minutes after the VM is active.")


if __name__ == "__main__":
    main()
