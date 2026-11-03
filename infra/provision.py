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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default="sjc")
    ap.add_argument("--plan", default="vc2-2c-4gb")
    ap.add_argument("--label", default="stunt-double")
    a = ap.parse_args()

    existing = [i for i in call("GET", "/instances?per_page=100").get("instances", []) if i["label"] == a.label]
    if existing:
        inst = existing[0]
        print(f"Instance already exists: {inst['id']} {inst['main_ip']} ({inst['status']})")
    else:
        os_id = next(o["id"] for o in call("GET", "/os?per_page=500")["os"] if o["name"].startswith("Ubuntu 24.04") and "x64" in o["name"])
        script = (pathlib.Path(__file__).parent / "setup-vultr.sh").read_text()
        key = os.environ.get("VULTR_INFERENCE_KEY", "")
        user_data = "#!/usr/bin/env bash\n" + (f"export VULTR_INFERENCE_KEY='{key}'\n" if key else "") + script.split("\n", 1)[1]
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
