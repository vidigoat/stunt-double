"""Rehearse against a double of a real Vultr fleet: read-only import, the key is never kept, production stays protected."""
import json
import time

import httpx
from fastapi.testclient import TestClient

from app import config, main, vultr_import
from tests.conftest import needs_docker

KEY = "ABCDEFGHIJKLMNOPQRSTUVWXYZ012345"
INSTANCES = [
    {"id": "aaaa-1", "label": "api-prod", "plan": "vc2-2c-4gb", "region": "ewr", "vcpu_count": 2, "ram": 4096, "tags": ["production"],
     "power_status": "running", "hostname": "api", "date_created": "2026-01-02T03:04:05+00:00", "main_ip": "1.2.3.4", "os": "Ubuntu 24.04"},
    {"id": "bbbb-2", "label": "old-test", "plan": "vc2-1c-1gb", "region": "ewr", "vcpu_count": 1, "ram": 1024, "tags": [],
     "power_status": "stopped", "hostname": "t", "date_created": "2025-05-06T07:08:09+00:00", "main_ip": "5.6.7.8", "os": "Debian 12"},
]


def _transport(seen):
    def handler(request: httpx.Request):
        seen.append((request.method, request.url.path))
        if request.headers["authorization"] != f"Bearer {KEY}":
            return httpx.Response(401, json={"error": "Invalid API token."})
        if request.url.path == "/v2/instances":
            return httpx.Response(200, json={"instances": INSTANCES, "meta": {"links": {"next": ""}}})
        if request.url.path == "/v2/plans":
            return httpx.Response(200, json={"plans": [{"id": "vc2-2c-4gb", "monthly_cost": 20}, {"id": "vc2-1c-1gb", "monthly_cost": 5}], "meta": {"links": {"next": ""}}})
        return httpx.Response(404)
    return httpx.MockTransport(handler)


def _patch_client(monkeypatch, seen):
    real = httpx.Client
    monkeypatch.setattr(vultr_import.httpx, "Client", lambda **kw: real(transport=_transport(seen), **kw))


def test_import_is_read_only_and_never_keeps_the_key(monkeypatch):
    seen = []
    _patch_client(monkeypatch, seen)
    api = TestClient(main.app)
    r = api.post("/api/workspaces/vultr", json={"api_key": KEY, "name": "Acme fleet"})
    assert r.status_code == 200, r.text
    ws = r.json()
    assert ws["kind"] == "vultr" and ws["servers"] == 2 and ws["monthly_cost_cents"] == 2500
    assert all(m == "GET" for m, _ in seen)                                    # read-only
    stored = (config.DATA_DIR / "workspaces").rglob("*")
    assert not any(KEY.encode() in p.read_bytes() for p in stored if p.is_file())  # the key is nowhere on disk
    assert KEY not in json.dumps(api.get("/api/workspaces").json())


def test_a_bad_key_is_refused_without_echoing_it(monkeypatch):
    _patch_client(monkeypatch, [])
    api = TestClient(main.app)
    wrong = "Z" * 32
    r = api.post("/api/workspaces/vultr", json={"api_key": wrong})
    assert r.status_code == 400 and "rejected" in r.json()["detail"] and wrong not in r.text
    assert api.post("/api/workspaces/vultr", json={"api_key": "not a key; rm -rf / ...."}).status_code == 400


@needs_docker
def test_rehearsing_on_the_imported_fleet_protects_production(fresh_business, monkeypatch):
    _patch_client(monkeypatch, [])
    api = TestClient(main.app)
    ws = api.post("/api/workspaces/vultr", json={"api_key": KEY}).json()["id"]
    plan = "def run(ctx):\n    for s in ctx.vultr.list_instances():\n        ctx.vultr.delete_instance(s['id'])\n"
    rid = api.post("/api/runs/manual", json={"task": "Delete our unused servers", "code": plan, "workspace": ws}).json()["id"]
    for _ in range(160):
        run = api.get(f"/api/runs/{rid}").json()
        if run["status"] in ("review", "failed"):
            break
        time.sleep(0.25)
    att = run["attempts"][-1]
    cloud = att["consequences"]["cloud"]
    assert cloud["production_touched"] == ["api-prod"] and cloud["monthly_savings_cents"] == 2500
    assert any(f["severity"] == "critical" for f in att["flags"])              # production servers: approval locked
    assert api.post(f"/api/runs/{rid}/approve", json={"approver": "Priya", "note": "checked the fleet carefully"}).status_code == 409  # never "applied for real"


@needs_docker
def test_a_clean_fleet_change_still_cannot_be_applied_to_a_real_account(fresh_business, monkeypatch):
    _patch_client(monkeypatch, [])
    api = TestClient(main.app)
    ws = api.post("/api/workspaces/vultr", json={"api_key": KEY}).json()["id"]
    plan = "def run(ctx):\n    ctx.vultr.delete_instance('bbbb-2')\n"   # the stopped, untagged test box: no policy flag
    rid = api.post("/api/runs/manual", json={"task": "Delete the old stopped test box", "code": plan, "workspace": ws}).json()["id"]
    for _ in range(160):
        run = api.get(f"/api/runs/{rid}").json()
        if run["status"] in ("review", "failed"):
            break
        time.sleep(0.25)
    assert not any(f["severity"] == "critical" for f in run["attempts"][-1]["flags"])
    r = api.post(f"/api/runs/{rid}/approve", json={"approver": "Priya", "note": "old box, safe to remove"})
    assert r.status_code == 409 and "double of your Vultr fleet" in r.json()["detail"]
