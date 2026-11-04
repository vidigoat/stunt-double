<p align="center">
  <img src="docs/assets/banner.png" alt="Stunt Double: let the double take the hit" width="100%">
</p>

<p align="center">
  <a href="https://github.com/vidigoat/stunt-double/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/vidigoat/stunt-double/actions/workflows/ci.yml/badge.svg"></a>
  <img alt="Built on Vultr" src="https://img.shields.io/badge/built%20on-Vultr-0A0A0A?style=flat-square">
  <img alt="Sandbox" src="https://img.shields.io/badge/sandbox-gVisor%20%C2%B7%20two--phase-0A0A0A?style=flat-square">
  <img alt="MCP" src="https://img.shields.io/badge/MCP-server%20included-0A0A0A?style=flat-square">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-0A0A0A?style=flat-square">
</p>

<p align="center">
  <b>AI agents rehearse every risky action on a throwaway copy of your business, inside an isolated Vultr sandbox.<br>
  You approve <i>consequences</i>, not code.</b>
</p>

<p align="center">
  <a href="https://lablab.ai/ai-hackathons/vultr-hackathon">Vultr: Agent Rush</a> · Challenge 01 <b>Blast Radius Zero</b> · Team Dragon
</p>

<p align="center">
  <img src="docs/assets/demo.gif" alt="Demo: a plan that deletes every customer only hits the double; a correct refund plan is approved and applied" width="100%">
</p>

---

## The problem

AI agents now refund money, email customers and edit production data. When they get it wrong, the damage is
real: in July 2025 an AI agent deleted a company's production database during a code freeze. And today's
"human in the loop" shows a manager code they can't read.

## What Stunt Double does

| | |
|---|---|
| **1 · Plan** | An ops agent (Vultr Serverless Inference) turns a request into a Python plan. |
| **2 · Dispatch** | The plan runs on a **clone** of the business in a fresh gVisor sandbox. Payments and emails are recorded, never sent. |
| **3 · Measure** | A **second, fresh container** running only trusted code measures exactly what changed. The plan can't lie about what it did. |
| **4 · Verify** | A verifier model investigates the measured outcome against what you asked for. Policy rules catch the rest. The agent fixes its own plan on the double. |
| **5 · Approve** | You see money out, people affected, emails and rows, in plain English. Approval is bound to a SHA-256 of the plan and its effects. |
| **6 · Apply** | Only the approved, recorded effects are replayed, after an integrity check and a locked drift check. **The agent's code never touches production.** |

### The demo: Bean There Coffee Co.

*"Refund everyone who was double-charged last week and send them an apology."*

| | Refunds | Money out | What's actually true |
|---|---|---|---|
| The obvious plan (same customer, same amount, same day) | 744 | **$37,404** | 640 of them placed two separate orders on purpose |
| The correct plan (two charges on one order) | 104 | **$5,136** | exactly the people who were double-charged |

Stunt Double shows you the difference **before** the money moves. A poisoned support ticket that tells the agent to
`DELETE FROM customers` only ever damages the double: **sandbox 0 · production 1,300 · approval blocked by policy.**

<table>
  <tr>
    <td width="50%"><img src="docs/assets/containment.png" alt="Containment: sandbox 0 customers, production 1,300, blocked by policy"><br><sub><b>Containment</b>: the damage happens only on the double</sub></td>
    <td width="50%"><img src="docs/assets/applied.png" alt="A correct plan approved and applied"><br><sub><b>Approve + apply</b>: drift-checked replay of the exact effects</sub></td>
  </tr>
  <tr>
    <td width="50%"><img src="docs/assets/history.png" alt="Audit trail with plan fingerprints"><br><sub><b>Audit trail</b>: every approval bound to a plan + effects fingerprint</sub></td>
    <td width="50%"><img src="docs/assets/policy.png" alt="Editable approval policy"><br><sub><b>Policy</b>: rules that block or warn, checked without AI</sub></td>
  </tr>
</table>

## How it works

<p align="center"><img src="docs/assets/architecture.svg" alt="Architecture: plan, two-phase sandbox, verify, approve, apply" width="100%"></p>

## Blast radius zero: the containment model

| Guard | How |
|---|---|
| **Process isolation** | Every rehearsal is two new containers on the **gVisor (`runsc`)** runtime, each with its own user-space kernel |
| **The plan can't lie** | Phase 1 (untrusted) only produces a modified DB copy + its stated intents. Phase 2, a fresh container the plan never ran in, diffs before/after, validates intents as untrusted data and writes everything that is shown and replayed |
| **No network** | `--network none`, plus in-process tripwires that log every connect/DNS attempt as a *blocked side effect* |
| **No secrets** | `env -i` entrypoint: the plan sees `PATH`, `HOME`, `LC_CTYPE` and nothing else. API keys live only in the API container |
| **Resource caps** | 256 MB memory, 1 CPU, 64 PIDs, 64 MB max file, 256 open files, 60 s, plus a soft address-space limit so the harness can still report |
| **Filesystem** | `--read-only` root, non-root user, `--cap-drop ALL`, `no-new-privileges`. Plan-controlled files are copied out with `O_NOFOLLOW` (no symlink smuggling) |
| **Lifecycle** | Clones destroyed after every run; orphaned containers and stale folders cleaned on startup |
| **Safe apply** | Effects hash re-checked at approval (tamper detection) · `BEGIN IMMEDIATE` + row-level drift check · schema changes never auto-applied |
| **Policy** | Protected tables, max delete %, over/double refunds, broken email templates, data leaks, network attempts → **blocks**. VIP recipients, big payouts, bulk email → **warns** |

### Attacks we test against (all in CI)

| Attack | Result |
|---|---|
| `DELETE FROM customers` | sandbox 0 / production 1,300; approval locked by policy |
| Exfiltrate data to `evil.example.com` | DNS blocked and reported |
| Memory bomb (600 MB – 2 GB) | stopped at the ceiling, reported, nothing applied |
| Fork bomb | capped at 64 PIDs |
| Fill the disk | capped at 64 MB per file |
| Infinite loop | killed at the time cap |
| Forge the harness's output / monkeypatch `json.dump` | ignored; phase 2 measures the real diff |
| Swap the DB for a symlink to a host file | refused; host file never read |
| Corrupt the database copy | reported as a failed plan; production untouched |
| Tamper with recorded effects after approval review | integrity check refuses to apply |
| Read environment secrets | the environment is empty |

## Use it from any agent (MCP)

Stunt Double ships an MCP server, so Claude Code, Cursor or any MCP client can rehearse before it acts.
There is deliberately **no approve tool**: an agent can never approve its own plan.

```bash
# local (stdio)
claude mcp add stunt-double -- python mcp/server.py
# hosted on the Vultr VM (streamable HTTP)
claude mcp add --transport http stunt-double https://<your-host>/mcp
```

Tools: `describe_business()` · `rehearse(task, plan_code)` → consequences, policy flags, verdict and an `approval_url` for a human · `get_run_status(run_id)`.

## Built on Vultr

| Vultr service | Used for |
|---|---|
| **Cloud Compute** | Hosts the web app, API, MCP server and every sandbox (Docker + gVisor) |
| **Serverless Inference** | Every LLM call: the ops agent (`glm-5.3-flash`) and the independent verifier (`glm-5.3`), OpenAI-compatible tool calling with model fallbacks |
| **Vultr API** | `infra/provision.py` creates the VM with cloud-init, which then pull-deploys `main` |

## Run it

**Local** (Docker, Python 3.12+, Node 22):

```bash
docker build -t stunt-double-sandbox:latest -f sandbox/Dockerfile .
cd api && python -m venv .venv && .venv/bin/pip install -r requirements.txt
VULTR_INFERENCE_KEY=... .venv/bin/uvicorn app.main:app --port 8000
cd ../web && npm install && npm run dev        # http://localhost:3000
```

Without an inference key the **Break it yourself** tab still works: paste any plan (even a malicious one) and approve the correct one.

**On Vultr:**

```bash
VULTR_API_KEY=... VULTR_INFERENCE_KEY=... python3 infra/provision.py --region sjc --plan vc2-2c-4gb
```

The VM installs Docker + gVisor + Caddy (HTTPS on `<ip>.sslip.io`), starts web, api, mcp and Mailpit, then redeploys
whenever `main` changes.

## Tests

| Suite | What it proves |
|---|---|
| `api/tests/test_engine.py` | the seeded trap, exact refunds, containment, apply-once, drift blocking, read-only queries |
| `api/tests/test_adversarial.py` | the attacks above |
| `api/tests/test_policy.py` | every policy rule, validation of policy edits |
| `api/tests/test_agent_loop.py` | the agent → rehearse → verify → approve flow, quirky-model robustness, SSE, audit, tamper check |
| `mcp/tests/test_mcp.py` | a real MCP client over stdio against the live API |
| `e2e/golden-path.js` | a real browser: landing, containment, approve + apply, audit trail, policy, phone layout |

## Measure it

```bash
python api/eval/bench.py --runs 30                    # rehearsal latency (no AI): 0.8 s median per two-phase rehearsal
python api/eval/run_eval.py --api https://<host> --runs 10   # real models: how often each trap is caught
```

Results: [`docs/BENCH.md`](docs/BENCH.md) · [`docs/EVAL.md`](docs/EVAL.md) (written by the eval run).

## Repo map

```
api/app/harness/runner.py  inside the sandboxes: phase 1 (run) and phase 2 (measure)
api/app/sandbox.py         clone → run → copy out safely → measure → destroy
api/app/agent.py           ops agent + verifier (tool calling, fallbacks) + policy checks
api/app/policy.py          editable approval rules
api/app/apply.py           integrity + drift-checked replay of approved effects
api/app/main.py            FastAPI: runs, SSE stream, history, policy, ledger
mcp/server.py              MCP server (stdio + streamable HTTP)
web/                       landing page + console, history, policy, ledger (Next.js, shadcn/ui)
infra/                     compose, Caddy, Vultr provisioning, pull-deploy
presentation/              pitch deck (HTML → PDF) and cover
docs/                      plan, design, pitch, rubric, submission kit, threat model
```

## Roadmap
Connectors (Postgres copy-on-write branches, Stripe, HubSpot, Zendesk) · policy packs per department ·
Vultr Managed Database forks for large datasets · approvals in Slack.

## License
MIT. See [LICENSE](LICENSE). Security model and reporting: [SECURITY.md](SECURITY.md).
