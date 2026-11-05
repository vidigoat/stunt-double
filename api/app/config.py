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
VERIFIER_MODEL = os.environ.get("SD_VERIFIER_MODEL", "glm-5.3-flash,qwen3.8-flash-next")  # Stunt Double's own checker (comma = fallbacks)
MAX_TOKENS = int(os.environ.get("SD_MAX_TOKENS", "16384"))  # flash models reason first; long plans need room
LLM_TIMEOUT_S = float(os.environ.get("SD_LLM_TIMEOUT", "120"))
AGENT_MAX_TURNS = int(os.environ.get("SD_AGENT_MAX_TURNS", "24"))

# Sandbox
SANDBOX_IMAGE = os.environ.get("SD_SANDBOX_IMAGE", "stunt-double-sandbox:latest")
SANDBOX_RUNTIME = os.environ.get("SD_SANDBOX_RUNTIME", "")           # "runsc" for gVisor on the Vultr VM
SANDBOX_MEMORY = os.environ.get("SD_SANDBOX_MEMORY", "256m")
SANDBOX_TIMEOUT_S = int(os.environ.get("SD_SANDBOX_TIMEOUT", "60"))
BROWSER_IMAGE = os.environ.get("SD_BROWSER_IMAGE", "stunt-double-browser:latest")  # plans that call ctx.browser
BROWSER_MEMORY = os.environ.get("SD_BROWSER_MEMORY", "1g")
BROWSER_TIMEOUT_S = int(os.environ.get("SD_BROWSER_TIMEOUT", "120"))
# Host path that maps to RUNS_DIR (needed when the API itself runs in a container and talks to the host Docker daemon)
RUNS_DIR_HOST = os.environ.get("SD_RUNS_DIR_HOST", str(RUNS_DIR))

# Real side effects (apply step only)
SMTP_HOST = os.environ.get("SD_SMTP_HOST", "localhost")
SMTP_PORT = int(os.environ.get("SD_SMTP_PORT", "1025"))

# Spend protection for the public demo: max AI-agent runs per UTC day (rehearsing pasted plans is free and unlimited).
DAILY_AGENT_RUNS = int(os.environ.get("SD_DAILY_AGENT_RUNS", "300"))
DAILY_VERIFICATIONS = int(os.environ.get("SD_DAILY_VERIFICATIONS", "400"))  # AI checks of hand-written plans, all visitors
# Mailpit's HTTP API (demo inbox), so a demo reset can empty it. Empty = don't touch any inbox.
MAILPIT_API = os.environ.get("SD_MAILPIT_API", "")
# Public site URL, used in links sent to humans (notifications). Empty = run ids only.
PUBLIC_URL = os.environ.get("SD_PUBLIC_URL", "")

# Dedicated Vultr VM isolation (opt-in per rehearsal). The key never enters a sandbox or a rehearsal VM.
VULTR_API_KEY = os.environ.get("SD_VULTR_API_KEY", "")
VM_PLAN = os.environ.get("SD_VM_PLAN", "vc2-1c-1gb")
VM_REGION = os.environ.get("SD_VM_REGION", "sjc")
VM_DAILY_LIMIT = int(os.environ.get("SD_VM_DAILY_LIMIT", "20"))
VM_SPEND_CEILING_USD = float(os.environ.get("SD_VM_SPEND_CEILING_USD", "30"))
# Postgres import: refuse private/internal hosts (tests and local development can allow them).
PG_ALLOW_PRIVATE = os.environ.get("SD_PG_ALLOW_PRIVATE", "") == "1"
SAMPLE_PG_URL = os.environ.get("SD_SAMPLE_PG_URL", "")  # the console's one-click sample database (internal, read-only)

# AI jury: independent models from other labs on Vultr Serverless Inference check every verification in parallel.
# The jury can make a verdict stricter, never more lenient. Empty disables it.
JURY_MODELS = [m for m in os.environ.get("SD_JURY_MODELS", "deepseek-v4.1-flash-1017,minimax-m3.1-flash").split(",") if m]
JURY_FALLBACK = os.environ.get("SD_JURY_FALLBACK", "qwen3.8-flash-next")
# Intent contracts: the model that writes down what a request means before any plan exists (comma = fallbacks).
DEMO_TODAY = "Tuesday 2026-11-03"   # the demo business's 'today' (the ops agent is told the same)
CONTRACT_MODELS = [m for m in os.environ.get("SD_CONTRACT_MODELS", "qwen3.8-flash-next,deepseek-v4.1-flash-1017").split(",") if m]
