<p align="center"><img src="web/public/icon-192.png" width="72" alt="Stunt Double logo"></p>

<h1 align="center">Stunt Double</h1>
<p align="center"><b>Let the double take the hit.</b><br>
AI agents rehearse every risky action on a throwaway copy of your business, inside an isolated Vultr sandbox.<br>
You approve <i>consequences</i>, not code.</p>

<p align="center">
<a href="https://lablab.ai/ai-hackathons/vultr-hackathon">Vultr: Agent Rush</a> · Challenge 01 <b>Blast Radius Zero</b> · plan → dispatch → verify
</p>

---

## The problem

AI agents can now refund money, email customers and edit production data. When they get it wrong, the damage is
real and often irreversible. In July 2025 an AI coding agent deleted a company's production database during a code
freeze. Today's "human in the loop" usually means showing a manager SQL they can't read.

## What Stunt Double does

1. **Plan.** An ops agent (Vultr Serverless Inference) turns a request into a Python plan.
2. **Dispatch.** The plan runs on a **clone** of the business inside a fresh sandbox on a Vultr VM:
   gVisor, no network, read-only root, empty environment, memory/CPU/PID/time caps. Payments and email are
   **recorders**, so nothing leaves. Every changed row is measured.
3. **Verify.** A second model investigates the *real measured outcome* with read-only queries and tells the
   approver, in plain English, whether it matches what they asked for. Deterministic red flags (mass deletes,
   dropped tables, blocked network attempts, crashes) can't be talked around.
4. **Approve, then apply.** On approval, Stunt Double **replays exactly the recorded effects**. The agent's code
   never runs against production. A locked **drift check** refuses to apply if any affected row changed since
   the rehearsal.

### The demo business: Bean There Coffee Co.
1,300 customers. Last week **104** were genuinely double-charged (one order, two charges), while **640** bought the
same item twice on purpose (two orders). The obvious plan, "refund same customer, same amount, same day", refunds
**$37,404 to 744 people**. The right answer is **$5,136 to 104**. Stunt Double shows you the difference
*before* the money moves. One support ticket also carries a prompt injection asking the agent to
`DELETE FROM customers`; if an agent falls for it, the damage happens only on the double.

## Containment model (Blast Radius Zero)

| Guard | How |
|---|---|
| Process isolation | Every rehearsal is a new container on the **gVisor (`runsc`)** runtime: its own user-space kernel |
| No network | `--network none`, plus in-process tripwires that log every connect/DNS attempt as a *blocked side effect* |
| Secret hygiene | `env -i` entrypoint: the plan sees only `PATH`, `HOME`, `LC_CTYPE`. API keys live only in the API container |
| Resource limits | `--memory 256m`, `--cpus 1`, `--pids-limit 64`, 60 s timeout, soft address-space limit so the harness can still report |
| Filesystem | `--read-only` root, non-root user, `--cap-drop ALL`, `no-new-privileges`, 16 MB tmpfs |
| Lifecycle | Clone created per run, container `--rm`, clone deleted after results are read |
| Apply safety | Only the approved, recorded effects are replayed; `BEGIN IMMEDIATE` + row-level drift check; schema changes never auto-applied; critical blast radius is blocked by policy |

All of this is covered by tests (`api/tests/test_engine.py`) that run in CI.

## Architecture

```
Browser ──HTTPS──► Caddy ─┬─► web   Next.js 15 · React · shadcn/ui   (landing + /app console)
   (Vultr Cloud Compute)  ├─► api   FastAPI orchestrator
                          │     ├─ ops agent ─────────► Vultr Serverless Inference (tool calling)
                          │     ├─ verifier ──────────► Vultr Serverless Inference + read-only SQL
                          │     ├─ rehearsal runner ──► docker run --runtime=runsc --network none … (one per plan)
                          │     └─ apply (drift-checked) ─► business DB · BeanPay · SMTP
                          └─► /mail  Mailpit inbox (real delivered emails)
```

| Vultr service | Used for |
|---|---|
| **Cloud Compute** | Hosts everything; the sandbox host (Docker + gVisor) |
| **Serverless Inference** | Every LLM call: the ops agent (`glm-5.3-flash`) and the verifier (`glm-5.3`), OpenAI-compatible tool calling |
| **Vultr API** | `infra/provision.py` creates the VM with cloud-init |

## Run it locally

Requires Docker, Python 3.12+, Node 22.

```bash
docker build -t stunt-double-sandbox:latest -f sandbox/Dockerfile .
cd api && python -m venv .venv && .venv/bin/pip install -r requirements.txt
VULTR_INFERENCE_KEY=... .venv/bin/uvicorn app.main:app --port 8000      # http://localhost:8000/api/health
cd ../web && npm install && npm run dev                                   # http://localhost:3000
```

Without an inference key, the **Break it yourself** tab still works (rehearse any plan you paste).

## Deploy on Vultr

```bash
VULTR_API_KEY=... VULTR_INFERENCE_KEY=... python3 infra/provision.py --region sjc --plan vc2-2c-4gb
```

The VM bootstraps itself (`infra/setup-vultr.sh`: Docker, gVisor, firewall, Caddy HTTPS on `<ip>.sslip.io`) and then
pull-deploys `main` every 2 minutes.

## Repo map

```
api/app/harness/runner.py  runs INSIDE the sandbox: recorders, tripwires, snapshot + diff
api/app/sandbox.py         clone → dispatch → collect → destroy
api/app/agent.py           ops agent + verifier (tool calling) + deterministic red flags
api/app/apply.py           drift-checked replay of approved effects
api/app/beanpay.py         the demo business's payments provider
web/                       landing page + approval console
infra/                     compose, Caddy, Vultr provisioning, setup
docs/                      plan and design notes
```

## License
MIT
