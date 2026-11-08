"""Optional: archive every decided run's evidence bundle to Vultr Object Storage (S3-compatible).

Enabled when SD_S3_ENDPOINT, SD_S3_ACCESS_KEY and SD_S3_SECRET_KEY are set (infra/provision.py --object-storage
creates them). Objects are written once per run under evidence/<yyyy-mm-dd>/<run_id>.json together with the
bundle's SHA-256, so the archive can be checked against the approval fingerprints later.
"""
import hashlib
import json
import os
import threading
import time

ENDPOINT = os.environ.get("SD_S3_ENDPOINT", "")          # e.g. https://sjc1.vultrobjects.com
BUCKET = os.environ.get("SD_S3_BUCKET", "stunt-double-evidence")
_lock = threading.Lock()
_client = None


def enabled() -> bool:
    return bool(ENDPOINT and os.environ.get("SD_S3_ACCESS_KEY") and os.environ.get("SD_S3_SECRET_KEY"))


def _s3():
    global _client
    with _lock:
        if _client is None:
            import boto3  # lazy: only needed when archiving is on
            _client = boto3.client("s3", endpoint_url=ENDPOINT, aws_access_key_id=os.environ["SD_S3_ACCESS_KEY"],
                                   aws_secret_access_key=os.environ["SD_S3_SECRET_KEY"], region_name=os.environ.get("SD_S3_REGION", "us-east-1"))
            try:
                _client.head_bucket(Bucket=BUCKET)
            except Exception:  # noqa: BLE001
                _client.create_bucket(Bucket=BUCKET)
        return _client


def archive(run_id: str, bundle: dict, stage: str = "") -> dict | None:
    """Upload one evidence bundle. Never raises: archiving must not block an approval."""
    if not enabled():
        return None
    body = json.dumps(bundle, default=str, sort_keys=True).encode()
    digest = hashlib.sha256(body).hexdigest()
    key = f"evidence/{time.strftime('%Y-%m-%d', time.gmtime())}/{run_id}{'-' + stage if stage else ''}.json"
    try:
        _s3().put_object(Bucket=BUCKET, Key=key, Body=body, ContentType="application/json", Metadata={"sha256": digest})
        return {"bucket": BUCKET, "key": key, "sha256": digest, "host": ENDPOINT.split("//")[-1], "bytes": len(body), "at": time.time()}
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)[:300]}


def link(key: str, seconds: int = 900) -> str | None:
    """A short-lived signed URL that downloads the archived object straight from Vultr Object Storage."""
    if not enabled():
        return None
    try:
        return _s3().generate_presigned_url("get_object", Params={"Bucket": BUCKET, "Key": key}, ExpiresIn=seconds)
    except Exception:  # noqa: BLE001
        return None
