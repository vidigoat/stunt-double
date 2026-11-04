import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

# Isolated data dir for the whole test session (must be set before app.config is imported).
os.environ.setdefault("SD_DATA_DIR", tempfile.mkdtemp(prefix="sd-test-"))
os.environ.setdefault("SD_SMTP_PORT", "1")  # nothing listens here: email delivery is counted as failed, not sent

ROOT = Path(__file__).resolve().parents[2]


def docker_ok() -> bool:
    return shutil.which("docker") is not None and subprocess.run(["docker", "info"], capture_output=True).returncode == 0


needs_docker = pytest.mark.skipif(not docker_ok(), reason="Docker daemon not available")


@pytest.fixture(scope="session", autouse=True)
def sandbox_image():
    if docker_ok():
        subprocess.run(["docker", "build", "-q", "-t", "stunt-double-sandbox:latest", "-f", str(ROOT / "sandbox" / "Dockerfile"), str(ROOT)],
                       check=True, capture_output=True)


@pytest.fixture()
def fresh_business():
    from app import beanpay, config, policy, seed
    seed.seed(config.PROD_DB)
    beanpay.reset()
    policy.reset()  # a policy saved by one test must never change another
    return config.PROD_DB


@pytest.fixture(autouse=True)
def reset_rate_limits():
    """Each test is a fresh 'visitor' for the per-IP rate limiter."""
    from app import main
    main.RATE.clear()
    yield
