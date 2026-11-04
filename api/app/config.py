"""Runtime configuration, all from environment variables."""
import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("SD_DATA_DIR", Path(__file__).resolve().parent.parent / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
PROD_DB = DATA_DIR / "business.db"          # "production" database of the demo business
BEANPAY_DB = DATA_DIR / "beanpay.db"        # ledger of the payments provider
RUNS_DIR = DATA_DIR / "runs"                # per-run artifacts (effects, consequences)
RUNS_DIR.mkdir(parents=True, exist_ok=True)

# Vultr Serverless Inference (OpenAI-compatible)
INFERENCE_BASE_URL = os.environ.get("VULTR_INFERENCE_BASE_URL", "https://api.vultrinference.com/v1")
INFERENCE_KEY = os.environ.get("VULTR_INFERENCE_KEY", "")
AGENT_MODEL = os.environ.get("SD_AGENT_MODEL", "glm-5.3-flash,qwen3.8-flash-next")  # the ops agent being supervised (comma = fallbacks)
VERIFIER_MODEL = os.environ.get("SD_VERIFIER_MODEL", "glm-5.3,qwen3.8-flash-next")  # Stunt Double's own checker (comma = fallbacks)
MAX_TOKENS = int(os.environ.get("SD_MAX_TOKENS", "8192"))
LLM_TIMEOUT_S = float(os.environ.get("SD_LLM_TIMEOUT", "120"))
AGENT_MAX_TURNS = int(os.environ.get("SD_AGENT_MAX_TURNS", "16"))

# Sandbox
SANDBOX_IMAGE = os.environ.get("SD_SANDBOX_IMAGE", "stunt-double-sandbox:latest")
SANDBOX_RUNTIME = os.environ.get("SD_SANDBOX_RUNTIME", "")           # "runsc" for gVisor on the Vultr VM
SANDBOX_MEMORY = os.environ.get("SD_SANDBOX_MEMORY", "256m")
SANDBOX_TIMEOUT_S = int(os.environ.get("SD_SANDBOX_TIMEOUT", "60"))
# Host path that maps to RUNS_DIR (needed when the API itself runs in a container and talks to the host Docker daemon)
RUNS_DIR_HOST = os.environ.get("SD_RUNS_DIR_HOST", str(RUNS_DIR))

# Real side effects (apply step only)
SMTP_HOST = os.environ.get("SD_SMTP_HOST", "localhost")
SMTP_PORT = int(os.environ.get("SD_SMTP_PORT", "1025"))

# Spend protection for the public demo: max AI-agent runs per UTC day (rehearsing pasted plans is free and unlimited).
DAILY_AGENT_RUNS = int(os.environ.get("SD_DAILY_AGENT_RUNS", "300"))
# Mailpit's HTTP API (demo inbox), so a demo reset can empty it. Empty = don't touch any inbox.
MAILPIT_API = os.environ.get("SD_MAILPIT_API", "")
# Public site URL, used in links sent to humans (notifications). Empty = run ids only.
PUBLIC_URL = os.environ.get("SD_PUBLIC_URL", "")
