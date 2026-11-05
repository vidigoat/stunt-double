"""Dedicated Vultr VM isolation, with the Vultr API and the VM simulated: the VM fetches a one-time bundle, returns a
modified database, our gVisor phase 2 measures it, the VM is always destroyed, and the guards fail closed."""
import io
import sqlite3
import tarfile
import threading
import time

import httpx
from fastapi.testclient import TestClient

from app import config, main, vultr_vm
from tests.conftest import needs_docker

PLAN = "def run(ctx):\n    ctx.db.execute(\"DELETE FROM customers\")\n"


class FakeVultr:
    """Records API calls; 'boots' a VM thread that behaves like the cloud-init script."""

    def __init__(self, api, pending=1.0, report=True):
        self.calls, self.api, self.pending, self.report = [], api, pending, report

    def __call__(self, method, path, **kw):
        self.calls.append((method, path))
        if path == "/account":
            return httpx.Response(200, json={"account": {"pending_charges": self.pending}})
        if method == "POST" and path == "/instances":
            token = next(iter(vultr_vm._jobs))
            if self.report:
                threading.Thread(target=self._vm, args=(token,), daemon=True).start()
            return httpx.Response(202, json={"instance": {"id": "11111111-2222-3333-4444-555555555555"}})
        if path.startswith("/instances?tag="):
            return httpx.Response(200, json={"instances": []})
        return httpx.Response(204)

    def _vm(self, token):
        time.sleep(0.3)
        bundle = self.api.get(f"/api/vm/{token}/bundle").content
        assert self.api.get(f"/api/vm/{token}/bundle").status_code == 404      # one-time
        with tarfile.open(fileobj=io.BytesIO(bundle)) as t:
            names = set(t.getnames())
            db = t.extractfile("work.db").read()
        assert names == {"plan.py", "work.db", "runner.py"}
        path = config.DATA_DIR / "vm-test.db"
        path.write_bytes(db)
        con = sqlite3.connect(path)
        con.execute("PRAGMA foreign_keys=OFF")
        for table in ("tickets", "subscriptions", "charges", "orders", "customers"):
            con.execute(f"DELETE FROM {table}")
        con.commit(); con.close()
        out = io.BytesIO()
        with tarfile.open(fileobj=out, mode="w:gz") as t:
            t.add(path, "work.db")
            for name, data in (("out/intents.json", b'{"payments": [], "emails": [], "logs": [], "blocked": [], "http": []}'), ("exit", b"0\n")):
                info = tarfile.TarInfo(name); info.size = len(data); t.addfile(info, io.BytesIO(data))
            evil = tarfile.TarInfo("../../etc/evil"); evil.size = 1; t.addfile(evil, io.BytesIO(b"x"))
        path.unlink()
        assert self.api.post(f"/api/vm/{token}/result", content=out.getvalue()).status_code == 200


def _configure(monkeypatch, fake):
    monkeypatch.setattr(config, "VULTR_API_KEY", "test-key")
    monkeypatch.setattr(config, "PUBLIC_URL", "https://example.test")
    monkeypatch.setattr(vultr_vm, "_api", fake)
    monkeypatch.setattr(vultr_vm, "BOOT_TIMEOUT_S", 20)
    vultr_vm._day.clear()


def _wait(api, rid):
    for _ in range(200):
        run = api.get(f"/api/runs/{rid}").json()
        if run["status"] in ("review", "failed"):
            return run
        time.sleep(0.25)
    return run


@needs_docker
def test_a_rehearsal_runs_on_its_own_vm_is_measured_here_and_the_vm_is_destroyed(fresh_business, monkeypatch):
    api = TestClient(main.app)
    fake = FakeVultr(api)
    _configure(monkeypatch, fake)
    rid = api.post("/api/runs/manual", json={"task": "Delete every customer", "code": PLAN, "isolation": "vultr_vm"}).json()["id"]
    run = _wait(api, rid)
    c = run["attempts"][-1]["consequences"]
    assert c["tables"]["customers"]["deleted"] == 1300                      # measured by our phase 2, not reported by the VM
    assert c["sandbox"]["isolation"] == "vultr_vm" and c["sandbox"]["vm"]["destroyed_at"]
    assert ("DELETE", "/instances/11111111-2222-3333-4444-555555555555") in fake.calls
    assert not (config.DATA_DIR.parent / "etc" / "evil").exists()
    assert api.get("/api/business").json()["counts"]["customers"] == 1300   # production untouched


@needs_docker
def test_a_vm_that_never_reports_back_fails_closed_and_is_still_destroyed(fresh_business, monkeypatch):
    api = TestClient(main.app)
    fake = FakeVultr(api, report=False)
    _configure(monkeypatch, fake)
    monkeypatch.setattr(vultr_vm, "BOOT_TIMEOUT_S", 3)
    rid = api.post("/api/runs/manual", json={"task": "Delete every customer", "code": PLAN, "isolation": "vultr_vm"}).json()["id"]
    c = _wait(api, rid)["attempts"][-1]["consequences"]
    assert c["ok"] is False and "did not report back" in c["error"]["message"]
    assert any(m == "DELETE" for m, _ in fake.calls)


@needs_docker
def test_the_spend_ceiling_stops_new_vms(fresh_business, monkeypatch):
    api = TestClient(main.app)
    fake = FakeVultr(api, pending=999.0)
    _configure(monkeypatch, fake)
    rid = api.post("/api/runs/manual", json={"task": "Delete every customer", "code": PLAN, "isolation": "vultr_vm"}).json()["id"]
    c = _wait(api, rid)["attempts"][-1]["consequences"]
    assert c["ok"] is False and "Spend ceiling" in c["error"]["message"]
    assert not any(m == "POST" for m, _ in fake.calls)


def test_vm_isolation_needs_configuration_and_is_not_for_browser_plans(monkeypatch):
    api = TestClient(main.app)
    monkeypatch.setattr(config, "VULTR_API_KEY", "")
    assert api.post("/api/runs/manual", json={"task": "x" * 10, "code": PLAN, "isolation": "vultr_vm"}).status_code == 400
    monkeypatch.setattr(config, "VULTR_API_KEY", "k")
    monkeypatch.setattr(config, "PUBLIC_URL", "https://example.test")
    browser = "def run(ctx):\n    ctx.browser.open('/subscriptions')\n"
    assert api.post("/api/runs/manual", json={"task": "x" * 10, "code": browser, "isolation": "vultr_vm"}).status_code == 400
    assert api.get("/api/vm/not-a-token/bundle").status_code == 404
    assert api.post("/api/vm/not-a-token/result", content=b"x").status_code == 404
