"""Evidence archiving to an S3-compatible store (Vultr Object Storage in production, moto here)."""
import hashlib
import json
import os
import time

import pytest
from fastapi.testclient import TestClient

from tests.conftest import needs_docker
from tests.test_engine import CORRECT

ENDPOINT = "https://sjc1.vultrobjects.com"
os.environ.setdefault("MOTO_S3_CUSTOM_ENDPOINTS", ENDPOINT)
moto = pytest.importorskip("moto")


@needs_docker
def test_decided_runs_are_archived(fresh_business, monkeypatch):
    from app import archive, main
    monkeypatch.setattr(archive, "ENDPOINT", ENDPOINT)
    monkeypatch.setattr(archive, "_client", None)
    monkeypatch.setenv("SD_S3_ACCESS_KEY", "test")
    monkeypatch.setenv("SD_S3_SECRET_KEY", "test")
    monkeypatch.setattr(main.config, "INFERENCE_KEY", "")
    with moto.mock_aws():
        api = TestClient(main.app)
        assert api.get("/api/health").json()["evidence_archive"] == "vultr-object-storage:stunt-double-evidence"
        rid = api.post("/api/runs/manual", json={"task": "Refund duplicates", "code": CORRECT}).json()["id"]
        for _ in range(80):
            if api.get(f"/api/runs/{rid}").json()["status"] == "review":
                break
            time.sleep(0.25)
        api.post(f"/api/runs/{rid}/approve", json={"approver": "Auditor test"})
        for _ in range(40):
            if (run := api.get(f"/api/runs/{rid}").json()).get("archive"):
                break
            time.sleep(0.25)
        a = run["archive"]
        assert a["bucket"] == "stunt-double-evidence" and a["key"].endswith(f"/{rid}.json"), a
        obj = archive._s3().get_object(Bucket=a["bucket"], Key=a["key"])
        body = obj["Body"].read()
        assert hashlib.sha256(body).hexdigest() == a["sha256"] == obj["Metadata"]["sha256"]
        assert json.loads(body)["approval"]["approver"] == "Auditor test"


def test_archiving_is_off_without_credentials(monkeypatch):
    from app import archive
    monkeypatch.setattr(archive, "ENDPOINT", "")
    assert archive.enabled() is False and archive.archive("run_x", {}) is None
